#!/usr/bin/env python
# Muyuan Chen 2021-03
from EMAN2 import *
import numpy as np

def main():
	
	usage="""
	New (2021) SPT refinement protocol including subtomogram, subtilt and defocus refinement. For a simple run, use
	e2spt_refine_new.py --ptcls sets/ptcls.lst --ref reference.hdf --iters p,p,t --startres 50 --goldstandard
	
	Control refinement modes with the --iters option. See details in the help below. 
	The program needs a resolution to be specified with --startres, which will be the maximum resolution considered in the first iteration. In later iterations, the maximum resolution is calculated from the FSC of the previous iteration. When --goldstandard is specified, the reference is phase randomized to the --startres resolution. 
	
	One major difference of the new protocol is that the program now can model the localized 2D particle motion by considering the motion trajectory of each particle along with its neighbors. For each particle, --smoothN controls how many of its neighbors are considered to model the local motion, and --smooth controls how much the neighboring particles are weighted during the alignment. The weight of neighboring particles decays in a Gaussian form based on the distance to the center particle of consideration. --smooth=0 means only the center particle is considered, and the program should perform in a similar way as the original subtilt refinement.
	
	"""
	parser = EMArgumentParser(usage=usage,version=EMANVERSION)
	parser.add_argument("--ptcls", type=str,help="3d particle input", default=None)
	parser.add_argument("--ref", type=str,help="reference map", default=None)
	parser.add_argument("--startres", type=float,help="Starting resolution for the refinement in A. Default is 50. This will be the maximum resolution considered for the first iteration. In later iterations, the maximum resolution is calculated from the FSC of the previous iteration (unless --maxres is specified).", default=50)

	parser.add_argument("--goldstandard", action="store_true", default=False, help="Phase randomize the reference to the starting resolution (--startres) independently for the even/odd subsets of particles.")
	parser.add_argument("--goldcontinue", action="store_true", default=False, help="Continue from previous gold standard refinement. Ues the _even/_odd version of the given reference.")

	#parser.add_argument("--restarget", default=0, type=float,help="The resolution you reasonably expect to achieve in the current refinement run (in A).")
	parser.add_argument("--maxres",type=float,help="Maximum resolution to consider in alignment (in A, not 1/A). The program will determine maximum resolution each round from the FSC of the previous round by default.",default=0)
	parser.add_argument("--minres",type=float,help="Minimum resolution to consider in alignment (in A, not 1/A)",default=0)
	parser.add_argument("--path", type=str,help="Directory of the refinement.", default=None)
	parser.add_argument("--sym", type=str,help="symmetry", default="c1")
	parser.add_argument("--iters", type=str,help="Iteration information. Input types of refinement separated by comma. p - 3d particle translation-rotation. t - subtilt translation. r - subtilt translation-rotation. d - subtilt defocus. Default is p,p,p,t,r,p,r,d. Character followed by number is also acceptable. p3 = p,p,p", default="p,p,p,t,r,p,r,d")
	parser.add_argument("--keep", type=str,help="Fraction of particles to keep. Note this is controlled at three separate steps. When default --keep=.95, it removes the worst 0.05 3D particles, 0.05 2D subtilt with the worst score, and 0.05 of subtilt with the largest drift. Also accept comma separated values (0.9,0.5,0.5) to set different keep thresholds for the three classes", default="0.95")
	parser.add_argument("--parallel","-P",type=str,help="Run in parallel, specify type:<option>=<value>:<option>=<value>. See http://blake.bcm.edu/emanwiki/EMAN2/Parallel",default="thread:4")
	parser.add_argument("--threads", type=int,help="threads for post-processing", default=10)
	parser.add_argument("--setsf", type=str,help="structure factor for sharpening", default=None)
	parser.add_argument("--tophat", type=str,help="tophat filter options, same as the single particle reconstruction.", default=None)
	parser.add_argument("--ssnrwt", action="store_true", default=False ,help="weight particles during reconstruction by SSNR accroding to references.")
	parser.add_argument("--curve", action="store_true", default=False ,help="Filament refinement mode. still under testing")
	parser.add_argument("--use3d", action="store_true", default=False ,help="Use projection of 3d particles instead of 2d sub tilt series. This may be more useful for thicker sample but can be significantly slower.")
	parser.add_argument("--localrefine", action="store_true", default=False ,help="only perform local search around the solution from the last iteration")
	parser.add_argument("--loadali2d", type=str,help="load previous 2d alignment from an aliptcls2d_xx.lst file", default=None)
	parser.add_argument("--loadali3d", type=str,help="load previous 3d alignment from an aliptcls3d_xx.lst file", default=None)
	parser.add_argument("--mask", type=str,help="Mask applied to the results (instead of automasking)", default=None)
	#parser.add_argument("--breaksym", type=str,help="Specify a symmetry to break", default=None) ## seems better to move this to e2spt_refinemulti_new.py
	parser.add_argument("--maskalign", type=str,help="Mask file applied to 3D alignment reference in each iteration. Not applied to the average, which will follow normal masking routine.", default=None)
	parser.add_argument("--maxshift", type=int, help="maximum shift. default box size/6",default=-1)
	parser.add_argument("--maxang", type=int, help="maximum angle difference from starting point for localrefine. ",default=30)
	parser.add_argument("--smooth",type=float,help="smooth local motion by this factor. smoother local motion with larger numbers. default 100",default=100)
	parser.add_argument("--smoothN",type=int,help="number of neighboring particles used for smoothing. default 15",default=15)

	(options, args) = parser.parse_args()
	logid=E2init(sys.argv)
	
	if options.path==None: options.path=num_path_new("spt_")
	path=options.path
	print(f"Writing in {path}...")
	
	#if options.restarget<1:
		#if options.goldstandard>1: options.restarget=options.goldstandard/2.0
		#else: options.restarget=options.startres/2.0
	
	#### the particle_info_xd.lst files will be used for every spt/subtilt program runs called by the refinement loop
	info2dname=f"{path}/particle_info_2d.lst"
	info3dname=f"{path}/particle_info_3d.lst"
	
	if os.path.isfile(info2dname) and os.path.isfile(info3dname):
		print("Using existing metadata files within the directory...")
		
	else:
		info2d, info3d = gather_metadata(options.ptcls)
		save_lst_params(info3d, info3dname)
		save_lst_params(info2d, info2dname)
		
	options.cmd=' '.join(sys.argv)
	fm=f"{path}/0_spt_params.json"
	js=js_open_dict(fm)
	js.update(vars(options))
	js.close()
	
	#### There were too many options controlling the resolution previously...
	##   --restarget is removed. It was only used in refine_postprocess when it align even/odd maps. 
	##   now the initial resolution is only controlled by --startres, and --goldstandard is now a bool
	##   so we randomphase the reference to --startres when --goldstandard is specified
	print("Preparing references...")
	opt=""
	res=options.startres
	if res<=0:
		print("ERROR: Starting resolution (resolution of the given reference) needed.")
		exit()
	if options.goldstandard==True and options.goldcontinue==False:
		refs={"even":options.ref, "odd":options.ref}
		opt+="--process filter.lowpass.gauss:cutoff_freq={r:.4f} --process filter.lowpass.randomphase:cutoff_freq={r:.4f}".format(r=1./res)
		
	else:	
		if options.goldcontinue:
			refs={eo:options.ref[:-4]+f"_{eo}.hdf" for eo in ["even","odd"]}
		else:
			print("WARNING: running without even/odd spliting. this could introduce model bias...")
			refs={"even":options.ref, "odd":options.ref}
	#if options.maxres!=0: res=options.maxres
	
	#### Scale reference based on particles.
	er=EMData(refs["even"],0,True)
	ep=EMData(info3dname,0,True)
	boxsize=ep["ny"]

	if abs(1-ep["apix_x"]/er["apix_x"])>0.01 or ep["ny"]!=er["ny"]:
		print("Reference-particle apix or box size mismatch. will scale/clip reference to match particles")
		if options.mask:
			print(" Please note the given mask will NOT be rescaled. Please scale/clip manually if needed")
			
		rs=er["apix_x"]/ep["apix_x"]
		if rs>1.:
			opt+=" --clip {} --scale {} --process mask.soft:outer_radius=-1".format(ep["nx"], rs)
		else:
			opt+=" --scale {} --clip {} --process mask.soft:outer_radius=-1".format(rs, ep["nx"])
		
	if options.maskalign!=None: opt+=f" --multfile {options.maskalign}"
	
	for eo in ["even", "odd"]:
		rf=refs[eo]
		run(f"e2proc3d.py {rf} {path}/threed_00_{eo}.hdf {opt}")
		
	run(f"e2proc3d.py {path}/threed_00_even.hdf {path}/threed_00.hdf --addfile {path}/threed_00_odd.hdf --mult 0.5")
		
	p2=EMData(info2dname,0,True)
	padsize=p2["ny"]
	
	last3d=last2d=None
	
	if options.loadali3d:
		fout=f"{path}/aliptcls3d_00.lst"
		run(f"e2proclst.py {options.loadali3d} --create {fout} ")
		last3d=fout
		
	if options.loadali2d:
		fout=f"{path}/aliptcls2d_00.lst"
		run(f"e2proclst.py {options.loadali2d} --create {fout} ")
		last2d=fout
		
	ppmask=setsf=tophat=""
	if options.setsf:
		setsf=f" --setsf {options.setsf}"
	if options.tophat:
		tophat=f" --tophat {options.tophat}"
	if options.mask:
		ppmask=f" --mask {options.mask}"
	if options.maskalign!=None: maskalign=EMData(options.maskalign,0)
	else: maskalign=None
	
	#### parse iteration string
	it0=options.iters.split(',')
	iters=[]
	for i in it0:
		if len(i)>1:
			r=int(i[1:])
			iters.extend([i[0]]*r)
		else:
			iters.append(i)
	keydic={'p':"Subtomogram alignment", 't': "Subtilt translational refinement", 'r': "Subtilt rotational refinement", 'd':"Defocus refinement"}
	
	#### now start the actual refinement loop
	for ii,itype in enumerate(iters):
		
		itr=ii+1
		ref=f"{path}/threed_{ii:02d}.hdf"
		print(f"######## iter {itr} ##########")
		print("### {}....".format(keydic[itype]))
		
		# Ok, this is a hack to avoid adding a new option to each subprogram. May be a little confusing if the program gets interrupted
		if options.maskalign!=None:
			for eo in ("even","odd"):
				tmp=f"{path}/tmpmsk_{eo}.hdf"
				refeo=f"{path}/threed_{ii:02d}_{eo}.hdf"
				refv=EMData(refeo,0)
				refv.write_compressed(tmp,0,12)
				refv.mult(maskalign)
				refv.write_compressed(refeo,0,12)

		# if there is a lot of variability, the overall resolution from the FSC may be a massive underestimate
		# which would then trigger the next iteration to not be aligned as well. This permits the user to
		# override the automatic value
		if options.maxres>0:
			res=options.maxres
			
		#### subtomogram alignment. 
		if itype=='p':
			opt=""
			ptcls=info3dname
			if options.localrefine and last3d:
				ptcls=last3d
				opt+=f" --maxshift {options.maxshift} --maxang {options.maxang}"
			if options.curve:
				opt+=" --curve"
			if options.localrefine==False and options.curve==False:
				opt+=" --fromscratch"
			
			#### if there is a subtilt alignment run before this, also use the 2d alignment info
			if last2d:
				opt+=f" --plst {last2d}"
			#if options.breaksym:
				#opt+=f" --breaksym {options.breaksym}"
			if options.use3d:
				opt+=" --use3d"
			if options.minres>0:
				opt+=f" --minres={options.minres}"
			if options.goldstandard>0 or options.goldcontinue:
				opt+=" --goldcontinue"
				
			cmd=f"e2spt_align_subtlt.py {ptcls} {ref} --path {path} --iter {itr} --maxres {res:.2f} --parallel {options.parallel} {opt}"
			run(cmd)
			
			last3d=f"{path}/aliptcls3d_{itr:02d}.lst"
			
		#### subtilt alignment, either including the rotation or not
		##   note a subtomogram alignment need to exist first
		if itype=='t' or itype=='r':
			if last3d==None:
				print("Need 3D particle alignment before subtilt refinement. exit.")
				exit()
				
			cmd=f"e2spt_subtlt_local.py --ref {ref} --path {path} --iter {itr} --maxres {res} --parallel {options.parallel} --refine_trans --aliptcls3d {last3d} --smooth {options.smooth} --smoothN {options.smoothN}"
			if itype=='r':
				cmd+=" --refine_rot"
			if options.maxshift>0:
				cmd+=f" --maxshift {options.maxshift}"
			if options.use3d:
				cmd+=" --use3d"
			if options.minres>0:
				cmd+=f" --minres={options.minres}"
			if options.goldstandard>0 or options.goldcontinue:
				cmd+=" --goldcontinue"
				
			run(cmd)
			last2d=f"{path}/aliptcls2d_{itr:02d}.lst"
				
		#### defocus refinement. not too useful but working...
		if itype=='d':
			if last2d==None or last3d==None:
				print("Need 3D and 2D particle alignment before defocus refinement. exit.")
				exit()
				
			cmd=f"e2spt_subtlt_local.py --ref {ref} --path {path} --iter {itr} --maxres {res} --parallel {options.parallel} --refine_defocus --aliptcls3d {last3d} --aliptcls2d {last2d}  --smooth {options.smooth} --smoothN {options.smoothN}"
			
			if options.minres>0:
				cmd+=f" --minres={options.minres}"
			if options.goldstandard>0 or options.goldcontinue:
				cmd+=" --goldcontinue"
			run(cmd)
			last2d=f"{path}/aliptcls2d_{itr:02d}.lst"
			
		#### always reconstruct 3d maps from 2d particles
		for eo in ["even", "odd"]:
			run(f"e2spa_make3d.py --input {path}/aliptcls2d_{itr:02d}.lst --output {path}/threed_{itr:02d}_{eo}.hdf --keep {options.keep} --clsid {eo} --parallel {options.parallel} --outsize {boxsize} --pad {padsize} --sym {options.sym}")
		
		#### only do SSNR weighting for the last iteration to avoid potential model bias
		##   simply run make3d a second time using the previous map as reference.
		if options.ssnrwt and itr==len(iters):
			run(f"e2refine_postprocess.py --even {path}/threed_{itr:02d}_even.hdf {setsf} --threads {options.threads} {ppmask}")
			res=calc_resolution(f"{path}/fsc_masked_{itr:02d}.txt")
			for eo in ["even", "odd"]:
				run(f"e2spa_make3d.py --input {path}/aliptcls2d_{itr:02d}.lst --output {path}/threed_{itr:02d}_{eo}.hdf --keep {options.keep} --clsid {eo} --parallel thread:{options.threads} --outsize {boxsize} --pad {padsize} --ref {path}/threed_{itr:02d}_{eo}.hdf --maxres {res} --sym {options.sym}")
			
		run(f"e2refine_postprocess.py --even {path}/threed_{itr:02d}_even.hdf {setsf} {tophat} --threads {options.threads} --restarget {res} --sym {options.sym} {ppmask}")

		res=calc_resolution(f"{path}/fsc_masked_{itr:02d}.txt")

		# put the unmasked file back again once we finish the iteration
		if options.maskalign!=None:
			for eo in ("even","odd"):
				tmp=f"{path}/tmpmsk_{eo}.hdf"
				refeo=f"{path}/threed_{ii:02d}_{eo}.hdf"
				os.unlink(refeo)
				os.rename(tmp,refeo)
	
	E2end(logid)
	
#### gather metadata from particles and return one dictionary for each 3d particle and one dictionary for each 2d one
##   for 3d particle, we keep the particle location coordinates, and a list of 2d particle indices that produces the 3d particle
##   for 2d particle, we keep the 3d particle index, the projection orientation with respect to the 3d particle, and the tilt id
def gather_metadata(pfile):
	print("Gathering metadata...")
	params=[]
	if pfile.endswith(".lst"):
		lst=LSXFile(pfile, True)
		nptcl=lst.n
		for i in range(nptcl):
			l=lst.read(i)
			params.append([l[1], l[0]])
			
		lst.close()
	
	else:
		nptcl=EMUtil.get_image_count(pfile)
		params=[[pfile, i] for i in range(nptcl)]
	
	info3d=[]
	info2d=[]
	for ii,pm in enumerate(params):
		img=EMData(pm[0], pm[1], True)
		imgsrc=img["class_ptcl_src"]
		imgidx=img["class_ptcl_idxs"]
		coord=img["ptcl_source_coord"]
		
		try: rhdrs=EMData.read_images(imgsrc,imgidx,IMAGE_UNKNOWN,True)
		except:
			print(f"couldn't read {imgidx} from {imgsrc}")
			sys.exit(1)
			
		idx2d=[]
		for k,i in enumerate(imgidx): 
			e=rhdrs[k]
			dc={"src":imgsrc,"idx":i,
				"idx3d":ii, "xform.projection":e["xform.projection"], "tilt_id":e["tilt_id"]}
			idx2d.append(len(info2d))
			info2d.append(dc)
		
		dc={"src":pm[0], "idx":pm[1], "coord":coord, "idx2d":idx2d}
		
		info3d.append(dc)

		sys.stdout.write("\r {}/{}".format(ii, len(params)))
		sys.stdout.flush()
	print()
		
	return info2d, info3d
	
	
#### here we use 0.2 cutoff as the 0.143 one is sometimes hard to find.
##   return a slightly higher resolution to use as the maxres for the next iteration
def calc_resolution(fscfile):
	fsc=np.loadtxt(fscfile)
	
	fi=fsc[:,1]<0.2
	if np.sum(fi)==0:
		print(f"WARNING: something wrong with the FSC curve ({fscfile}). Cannot estimate resolution. Please check.")
		rs=1./fsc[-2,0]
	else:
		rs=1./fsc[fi, 0][0]
		print("Resolution (FSC<0.2) is ~{:.1f} A".format(rs))
	
	return rs*.8
	
def run(cmd):
	print(cmd)
	launch_childprocess(cmd)
	
if __name__ == '__main__':
	main()
	
