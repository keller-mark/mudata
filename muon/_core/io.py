from typing import Union
from pathlib import Path
import os

import numpy as np
import anndata as ad
from anndata import AnnData
from pathlib import Path
import scanpy as sc
from .mudata import MuData

from .._atac.tools import add_peak_annotation, locate_fragments, add_peak_annotation_gene_names

# 
# Reading data
# 

def read_10x_h5(filename: Union[str, Path],
				extended: bool = True,
				*args, **kwargs) -> MuData:
	"""
	Read data from 10X Genomics-formatted HDF5 file

	This function uses scanpy.read_10x_h5() internally 
	and patches its behaviour to:
	- attempt to read `interval` field for features;
	- attempt to locate peak annotation file and add peak annotation;
	- attempt to locate fragments file.

	Ideally it is merged later to scanpy.read_10x_h5().

	Parameters
	----------
	filename : str
		Path to 10X HDF5 file (.h5)
	extended : bool, optional (default: True)
		Perform extended functionality automatically such as
		locating peak annotation and fragments files.
	"""

	adata = sc.read_10x_h5(filename, gex_only=False, *args, **kwargs)

	# Patches sc.read_10x_h5 behaviour to:
	# - attempt to read `interval` field for features from the HDF5 file
	# - attempt to add peak annotation
	# - attempt to locate fragments file

	if extended:

		# 1) Read interval field from the HDF5 file

		try:
			import h5py
		except ImportError:
			raise ImportError(
				"h5py is not available. Install h5py from PyPI (`pip install pypi`) or from GitHub (`pip install git+https://github.com/h5py/h5py`)"
				)

		h5file = h5py.File(filename, 'r')

		if 'interval' in h5file["matrix"]["features"]:
			intervals = np.array(h5file["matrix"]["features"]["interval"]).astype(str)

			h5file.close()

			adata.var["interval"] = intervals

			print(f"Added `interval` annotation for features from {filename}")

		else:
			# Make sure the file is closed
			h5file.close()

	mdata = MuData(adata)

	if extended:
		if 'atac' in mdata.mod:
		
			# 2) Add peak annotation

			default_annotation = os.path.join(os.path.dirname(filename), "atac_peak_annotation.tsv")
			if os.path.exists(default_annotation):
				add_peak_annotation(mdata.mod['atac'], default_annotation)
				print(f"Added peak annotation from {default_annotation} to .uns['atac']['peak_annotation']")

			try:
				add_peak_annotation_gene_names(mdata)
				print("Added gene names to peak annotation in .uns['atac']['peak_annotation']")
			except Exception:
				pass

			# 3) Locate fragments file

			default_fragments = os.path.join(os.path.dirname(filename), "atac_fragments.tsv.gz")
			if os.path.exists(default_annotation):
				locate_fragments(mdata.mod['atac'], default_fragments)
				print(f"Located fragments file: {default_fragments}")

	return mdata


# 
# Saving multimodal data objects 
# 

def write_h5mu(filename: Union[str, Path],
			   mdata: MuData,
			   *args, **kwargs):
	"""
	Write MuData object to the HDF5 file

	Currently is based on anndata._io.h5ad.write_h5ad internally.
	Matrices - sparse or dense - are currently stored as they are.

	Ideally this is merged later to anndata._io.h5ad.write_h5ad.
	"""
	
	try:
		import h5py
	except ImportError:
		raise ImportError(
			"h5py is not available but is required to write .h5mu files. Install h5py from PyPI (`pip install h5py`) \
			or from GitHub (`pip install git+https://github.com/h5py/h5py`)"
			)

	from anndata._io.utils import write_attribute
	from anndata._io.h5ad import write_h5ad

	write_h5ad(filepath=filename, adata=mdata, *args, **kwargs)

	with h5py.File(filename, "a") as f:
		# Remove modalities if they exist
		if 'mod' in f:
			del f['mod']
		mod = f.create_group('mod')
		for k, v in mdata.mod.items():
			mod.create_group(k)

			adata = mdata.mod[k]

			adata.strings_to_categoricals()
			if adata.raw is not None:
				adata.strings_to_categoricals(adata.raw.var)

			write_attribute(f, f"mod/{k}/X", adata.X)
			write_attribute(f, f"mod/{k}/raw", adata.raw)
  
			write_attribute(f, f"mod/{k}/obs", adata.obs)
			write_attribute(f, f"mod/{k}/var", adata.var)
			write_attribute(f, f"mod/{k}/obsm", adata.obsm)
			write_attribute(f, f"mod/{k}/varm", adata.varm)
			write_attribute(f, f"mod/{k}/obsp", adata.obsp)
			write_attribute(f, f"mod/{k}/varp", adata.varp)
			write_attribute(f, f"mod/{k}/layers", adata.layers)
			write_attribute(f, f"mod/{k}/uns", adata.uns)


def write_h5ad(filename: Union[str, Path],
			   mod: str,
			   data: Union[MuData, AnnData]):
	"""
	Write AnnData object to the HDF5 file with a MuData container

	Currently is based on anndata._io.h5ad.write_h5ad internally.
	Matrices - sparse or dense - are currently stored as they are.

	Ideally this is merged later to anndata._io.h5ad.write_h5ad.
	"""
	
	try:
		import h5py
	except ImportError:
		raise ImportError(
			"h5py is not available but is required to write .h5mu files. Install h5py from PyPI (`pip install h5py`) \
			or from GitHub (`pip install git+https://github.com/h5py/h5py`)"
			)

	from anndata._io.utils import write_attribute
	from anndata._io.h5ad import write_h5ad

	if isinstance(data, AnnData):
		adata = data
	elif isinstance(data, MuData):
		adata = data.mod[mod]
	else:
		raise TypeError(f"Expected AnnData or MuData object with {mod} modality")

	with h5py.File(filename, 'r+') as f:
		# Check that 'mod' is present
		if not 'mod' in f:
			raise ValueError("The .h5mu object has to contain .mod slot")
		fm = f['mod']

		# Remove the modality if it exists
		if mod in fm:
			del fm[mod]

		fmd = fm.create_group(mod)

		adata.strings_to_categoricals()
		if adata.raw is not None:
			adata.strings_to_categoricals(adata.raw.var)
		
		filepath = Path(filename)

		if not (adata.isbacked and Path(adata.filename) == Path(filepath)):
			write_attribute(f, f"mod/{mod}/X", adata.X)
		write_attribute(f, f"mod/{mod}/raw", adata.raw)

		write_attribute(f, f"mod/{mod}/obs", adata.obs)
		write_attribute(f, f"mod/{mod}/var", adata.var)
		write_attribute(f, f"mod/{mod}/obsm", adata.obsm)
		write_attribute(f, f"mod/{mod}/varm", adata.varm)
		write_attribute(f, f"mod/{mod}/obsp", adata.obsp)
		write_attribute(f, f"mod/{mod}/varp", adata.varp)
		write_attribute(f, f"mod/{mod}/layers", adata.layers)
		write_attribute(f, f"mod/{mod}/uns", adata.uns)


write_anndata = write_h5ad


def write(filename: Union[str, Path],
		  data: Union[MuData, AnnData]):
	"""
	Write MuData or AnnData to an HDF5 file

	This function is designed to enhance I/O ease of use.
	It recognises the following formats of filename:
	  - for MuData
		- FILE.h5mu
	  - for AnnData
		  - FILE.h5mu/MODALITY
		  - FILE.h5mu/mod/MODALITY
		  - FILE.h5ad
	"""

	import re

	if filename.endswith(".h5mu") or isinstance(data, MuData):
		assert filename.endswith(".h5mu") and isinstance(data, MuData), \
		"Can only save MuData object to .h5mu file"

		write_h5mu(filename, data)

	else:
		assert isinstance(data, AnnData), "Only MuData and AnnData objects are accepted"

		m = re.search("^(.+)\.(h5mu)[/]?([A-Za-z]*)[/]?([/A-Za-z]*)$", filename)
		if m is not None:
			m = m.groups()
		else:
			raise ValueError("Expected non-empty .h5ad or .h5mu file name")

		filepath = ".".join([m[0], m[1]])

		if m[1] == "h5mu":
			if m[3] == "":
				# .h5mu/<modality>
				return write_h5ad(filepath, m[2], data)
			elif m[2] == "mod":
				# .h5mu/mod/<modality>
				return write_h5ad(filepath, m[3], data)
			else:
				raise ValueError("If a single modality to be written from a .h5mu file, \
					provide it after the filename separated by slash symbol:\
					.h5mu/rna or .h5mu/mod/rna")
		elif m[1] == "h5ad":
			return data.write(filepath)
		else:
			raise ValueError()

# 
# Reading from multimodal data objects
# 

def read_h5mu(filename: Union[str, Path]):
	"""
	Read MuData object from HDF5 file
	"""
	try:
		import h5py
	except ImportError:
		raise ImportError(
			"h5py is not available but is required to read .h5mu files. Install h5py from PyPI (`pip install h5py`) \
			or from GitHub (`pip install git+https://github.com/h5py/h5py`)"
			)

	from anndata._io.utils import read_attribute
	from anndata._io.h5ad import read_dataframe

	with h5py.File(filename, "r") as f:
		d = {}
		for k in f.keys():
			if k in ["obs", "var"]:
				d[k] = read_dataframe(f[k])
			else:
				d[k] = read_attribute(f[k])

	return MuData._init_from_dict_(**d)

def read_h5ad(
	filename: Union[str, Path],
	mod: str,
	backed: Union[str, bool, None] = None,
	) -> AnnData:
	"""
	Read AnnData object from inside a .h5mu file 
	or from a standalone .h5ad file

	Currently replicates and modifies anndata._io.h5ad.read_h5ad.
	Matrices are loaded as they are in the file (sparse or dense).

	Ideally this is merged later to anndata._io.h5ad.read_h5ad.
	"""
	try:
		import h5py
	except ImportError:
		raise ImportError(
			"h5py is not available but is required to read .h5mu files. Install h5py from PyPI (`pip install h5py`) \
			or from GitHub (`pip install git+https://github.com/h5py/h5py`)"
			)

	assert backed in [None, True, False, "r", "r+"], "Argument `backed` should be boolean, or r/r+, or None"

	from anndata._io.utils import read_attribute
	from anndata._io.h5ad import read_dataframe, _read_raw, _clean_uns

	d = {}

	hdf5_mode = "r"
	if backed not in {None, False}:
		hdf5_mode = backed
		if hdf5_mode is True:
			hdf5_mode = "r+"
		assert hdf5_mode in {"r", "r+"}

		d.update({"filename": filename, "mode": hdf5_mode})

	with h5py.File(filename, hdf5_mode) as f_root:
		f = f_root['mod'][mod]
		for k in f.keys():
			if k in ["obs", "var"]:
				d[k] = read_dataframe(f[k])
			else:
				d[k] = read_attribute(f[k])

		d["raw"] = _read_raw(f)

		X_dset = f.get("X", None)
		if X_dset is None:
			pass
		elif isinstance(X_dset, h5py.Group):
			d["dtype"] = X_dset["data"].dtype
		elif hasattr(X_dset, "dtype"):
			d["dtype"] = f["X"].dtype
		else:
			raise ValueError()

	return AnnData(**d)


read_anndata = read_h5ad


def read(filename: Union[str, Path]) -> Union[MuData, AnnData]:
	"""
	Read MuData object from HDF5 file 
	or AnnData object (a single modality) inside it

	This function is designed to enhance I/O ease of use.
	It recognises the following formats:
	  - FILE.h5mu
	  - FILE.h5mu/MODALITY
	  - FILE.h5mu/mod/MODALITY
	  - FILE.h5ad
	"""
	try:
		import h5py
	except ImportError:
		raise ImportError(
			"h5py is not available but is required to read .h5mu files. Install h5py from PyPI (`pip install h5py`) \
			or from GitHub (`pip install git+https://github.com/h5py/h5py`)"
			)

	import re

	m = re.search("^(.+)\.(h5mu)[/]?([A-Za-z]*)[/]?([/A-Za-z]*)$", filename)
	if m is not None:
		m = m.groups()
	else:
		raise ValueError("Expected non-empty .h5ad or .h5mu file name")

	filepath = ".".join([m[0], m[1]])

	if m[1] == "h5mu":
		if all(i == 0 for i in map(len, m[2:])):
			# Ends with .h5mu
			return read_h5mu(filepath)
		elif m[3] == "":
			# .h5mu/<modality>
			return read_h5ad(filepath, m[2])
		elif m[2] == "mod":
			# .h5mu/mod/<modality>
			return read_h5ad(filepath, m[3])
		else:
			raise ValueError("If a single modality to be read from a .h5mu file, \
				provide it after the filename separated by slash symbol:\
				.h5mu/rna or .h5mu/mod/rna")
	elif m[1] == "h5ad":
		return ad.read_h5ad(filepath)
	else:
		raise ValueError()