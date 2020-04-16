
import sys

kernel = sys.argv[1]
graph = sys.argv[2]
print("process0 = { \n" + \
    "command = \"/root/git/742Project/gapbs/{} -f /root/git/742Project/edgelist_data/{}.mtx -n 1 -s\" \n".format(kernel, graph)+\
    "\tstartFastForwarded = True; \n};");
