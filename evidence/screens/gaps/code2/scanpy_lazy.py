import resource, anndata as ad, h5py
rss = lambda: resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20  # MB (macOS: bytes)
print(f"anndata {ad.__version__}; max RSS at start {rss():.0f} MB")
a = ad.read_h5ad("bm_demo.h5ad", backed="r")           # X stays on disk
print(a)
print("X:", type(a.X).__name__, "| max RSS after open", f"{rss():.0f} MB")
g = a[:, "Mpo"].X                                        # one gene read from disk
print("one gene:", type(g).__name__, g.shape, "| max RSS", f"{rss():.0f} MB")
a.file.close()
lz = ad.experimental.read_lazy(h5py.File("bm_demo.h5ad", "r"))
print("read_lazy X:", type(lz.X).__name__, lz.X.shape, "| obsp keys:", list(lz.obsp.keys()))
