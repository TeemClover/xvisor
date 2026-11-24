"""print the clip names of edl.py, one per line"""
import common
print("\n".join(c["name"] for c in common.load_edl().CLIPS))
