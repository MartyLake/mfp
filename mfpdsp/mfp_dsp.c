#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "mfp_dsp.h"


int mfp_dsp_enabled = 0;
int mfp_needs_reschedule = 1;

static int 
depth_cmp_func(const void * a, const void *b) 
{
	if ((*(mfp_processor **) a)->depth < (*(mfp_processor **)b)->depth) 
		return -1;
	else if ((*(mfp_processor **) a)->depth == (*(mfp_processor **)b)->depth)
		return 0;
	else 
		return 1;
}


static int
ready_to_schedule(mfp_processor * p)
{
	int icount;
	int ready = 1;
	GArray * infan;
	mfp_connection ** ip;
	int maxdepth = -1;

	if (p->typeinfo->is_generator == 1) {
		return 0;
	}

	for (icount = 0; icount < p->inlet_conn->len; icount++) {
		infan = g_array_index(p->inlet_conn, GArray *, icount);
		for(ip = (mfp_connection **)(infan->data); *ip != NULL; ip++) {
			if ((*ip)->dest_proc->depth < 0) {
				ready = 0;
				break;
			}
			else if ((*ip)->dest_proc->depth > maxdepth) {
				maxdepth = (*ip)->dest_proc->depth;
			}
		}
		if (ready == 0) {
			break;
		}
	}

	if (ready > 0) {
		return maxdepth + 1;
	}
	else {
		return -1;
	}
}

int 
mfp_dsp_schedule(void) 
{
	int pass = 0;
	int lastpass_unsched = -1;
	int thispass_unsched = 0;
	int another_pass = 1;
	int proc_count = 0;
	int depth = -1;
	mfp_processor ** p;

	/* unschedule everything */
	for (p = (mfp_processor **)(mfp_proc_list->data); *p != NULL; p++) {
		(*p)->depth = -1;
		proc_count ++;
	}

	/* calculate scheduling order */ 
	while (another_pass == 1) {
		for (p = (mfp_processor **)(mfp_proc_list->data); *p != NULL; p++) {
			if ((*p)->depth < 0) {
				depth = ready_to_schedule(*p);
				if (depth >= 0) {
					(*p)->depth = depth;
				}
				else {
					thispass_unsched++;
				}
			}
		}
		if ((thispass_unsched > 0) && 
			(lastpass_unsched < 0 || (thispass_unsched < lastpass_unsched))) {
			another_pass = 1;
		}
		else {
			another_pass = 0;
		}
		lastpass_unsched = thispass_unsched;
		thispass_unsched = 0;
		pass ++;
	}
	
	/* conclusion: either success, or a DSP loop */
	if (lastpass_unsched > 0) {
		/* DSP loop: some processors not scheduled */ 
		return 0;
	}
	else {
		/* sort processors in place by depth */ 
		g_array_sort(mfp_proc_list, depth_cmp_func);
		return 1;
	}
}

/*
 * mfp_dsp_run is the bridge between JACK processing and the MFP DSP 
 * network.  It is called once per JACK block from the process() 
 * callback.
 */

void
mfp_dsp_run(int nsamples) 
{
	mfp_processor ** p;

	mfp_dsp_set_blocksize(nsamples);

	if (mfp_needs_reschedule == 1) {
		if (!mfp_dsp_schedule()) {
			printf("DSP Error: Some processors could not be scheduled\n");
		}
		mfp_needs_reschedule = 0;
	}

	/* the proclist is already scheduled, so iterating in order is OK */
	for(p = (mfp_processor **)(mfp_proc_list->data); *p != NULL; p++) {
		mfp_proc_process(*p);
	}

}

void
mfp_dsp_set_blocksize(int nsamples) 
{
	mfp_blocksize = nsamples;

	/* FIXME need to inform all processors so to reallocate buffers */ 
}

void
mfp_dsp_accum(mfp_sample * accum, mfp_sample * addend, int blocksize)
{
	int i;
	if ((accum == NULL) || (addend == NULL)) {
		return;
	}

	for (i=0; i < blocksize; i++) {
		accum[i] += addend[i];
	}
}

