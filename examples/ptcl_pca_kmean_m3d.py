#!/usr/bin/env python
# Muyuan Chen 2020-03
from EMAN2 import *
import numpy as np
from sklearn import cluster,mixture
from sklearn.decomposition import PCA

def main():
	
	usage=" "
	parser = EMArgumentParser(usage=usage,version=EMANVERSION)
	parser.add_argument("--pts", type=str,help="point input", default="")
	parser.add_argument("--pcaout", type=str,help="pca output", default="")
	parser.add_argument("--ptclsin", type=str,help="ptcl input", default="")
	parser.add_argument("--ptclsout", type=str,help="ptcl out suffix", default="")
	parser.add_argument("--pad", type=int,help="pad for make3d", default=-1)
	parser.add_argument("--ncls", type=int,help="number of classes", default=3)
	parser.add_argument("--nbasis", type=int,help="PCA dimensionality", default=2)
	parser.add_argument("--setsf", type=str,help="setsf", default="")
	parser.add_argument("--mode", type=str,help="classify/regress", default="classify")
	parser.add_argument("--nptcl", type=int,help="number of particles per class in regress mode", default=2000)
	parser.add_argument("--threads", default=12,type=int,help="Number of threads to run in parallel on a single computer. This is the only parallelism supported by e2make3dpar")
	(options, args) = parser.parse_args()
	logid=E2init(sys.argv)
	
	pts=np.loadtxt(options.pts)
	
	pca=PCA(options.nbasis)
	p2=pca.fit_transform(pts[:,1:])
	if options.pcaout:
		np.savetxt(options.pcaout, p2)

	if options.mode=="classify":
		clust=cluster.KMeans(options.ncls)
		lbs=clust.fit_predict(p2)
		lbunq=np.unique(lbs)
		
	else:
		p=p2[:,0]
		print(np.max(abs(p)))
		rg=np.arange(options.ncls)
		rg=rg/np.max(rg)-.5
		mx=2*np.sort(abs(p))[int(len(p)*.9)]
		print(np.sort(abs(p)))
		print(mx)
		rg=rg*mx+np.mean(p)
		
		
	onames=[]
	fname=options.ptclsin
	lstinp=fname.endswith(".lst")
	
	if lstinp:
		lin=LSXFile(fname)
		
	for j in range(options.ncls):
		
		onm="{}_{:02d}.lst".format(options.ptclsout, j)
		
		if options.mode=="classify":
			l=lbunq[j]
			ii=(lbs==l)
			print(onm, np.sum(ii))
		else:
			d=abs(p2[:,0]-rg[j])
			ii=np.argsort(d)[:options.nptcl]
			print(onm, rg[j], d[ii[-1]])
		
		idx=pts[ii,0].astype(int)
		
		if os.path.isfile(onm):
			os.remove(onm)
		lout=LSXFile(onm, False)
		for i in idx:
			if lstinp:
				l=lin.read(i)
				lout.write(-1, l[0], l[1])
			else:
				lout.write(-1, i, fname)
			
		lout=None
		onames.append(onm)
	
	e=EMData(fname, 0, True)
	if options.pad<1: options.pad=good_size(e["nx"]*1.25)
	if options.setsf:
		options.setsf=" --setsf "+options.setsf
	
	for o in onames:
		t=o[:-3]+"hdf"
		print(o,t)
		cmd="e2make3dpar.py --input {} --output {} --pad {} --mode trilinear --no_wt --keep 1 --threads {} {}".format(o,t, options.pad, options.threads, options.setsf)
		launch_childprocess(cmd)
	
	E2end(logid)
	
def run(cmd):
	print(cmd)
	launch_childprocess(cmd)
	
	
if __name__ == '__main__':
	main()
	
