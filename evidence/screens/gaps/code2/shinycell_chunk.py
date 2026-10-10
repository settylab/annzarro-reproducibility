# Which bytes of sc1gexpr.h5 hold one gene: the HDF5 chunk index of the dataset ShinyCell reads.
import os, h5py
f = h5py.File("sc1gexpr.h5", "r"); d = f["grp/data"]
print(f"grp/data {d.shape} (cells x genes), {d.dtype}, {d.compression}, chunks {d.chunks}: {d.id.get_num_chunks():,} chunks")
ci = d.id.get_chunk_info_by_coord((0, 10419))          # Mpo, gene 10420 (1-based in R)
size = os.path.getsize("sc1gexpr.h5")
print(f"Mpo chunk: offset {ci.byte_offset:,}, {ci.size:,} bytes stored = {100 * ci.size / size:.3f}% of the {size:,}-byte file")
