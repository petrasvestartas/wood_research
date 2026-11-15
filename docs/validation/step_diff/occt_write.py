# occt_write.py <in.step> <out.step>: OCCT reads and writes the file again (AP214, as read)
import sys
from OCP.STEPControl import STEPControl_Reader, STEPControl_Writer, STEPControl_AsIs
r = STEPControl_Reader(); r.ReadFile(sys.argv[1]); r.TransferRoots()
w = STEPControl_Writer(); w.Transfer(r.OneShape(), STEPControl_AsIs); w.Write(sys.argv[2])
