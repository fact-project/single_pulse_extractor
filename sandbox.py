#!/usr/bin/env python
from __future__ import absolute_import, print_function, division
import numpy as np
import matplotlib.pyplot as plt
from scipy import signal
import random
from tqdm import tqdm
import matplotlib.patches as mpatches
#-------------------------------------------------------------------------------
class Bench(object):
    def __init__(self):
        self.truePositive = 0
        self.falsePositive = 0
        self.trueNegative = 0
        self.falseNegative = 0

    def truePositiveRate(self):
        return self.truePositive/(self.truePositive + self.falseNegative)

    def falseNegativeRate(self):
        return self.falsePositive/(self.truePositive + self.falseNegative)

    def __str__(self):
        out=''
        out+='correct positive rate '+str(self.truePositiveRate())
        out+='false negative rate '+str(self.falseNegativeRate())
        return out
#-------------------------------------------------------------------------------
def time_slices(f_sample, N):
    """
    Sample moment times

    Parameters
    ----------
    f_sample    scalar like, sample frequency of a timeline
    N           scalar like, number of samples on a timeline

    Returns
    -------
    Returns the sample moment times (array like) of a timeline of length N 
    and with sample frequency f_sample.
    """
    return np.linspace(0, N/f_sample, num=N, endpoint=False)
#-------------------------------------------------------------------------------
def power_spectrum(sig_vs_t, f_sample):
    """
    Power frequecy spectrum of a signal time line sig_vs_t of sample frequency f_sample

    Parameters
    ----------
    sig_vs_t    array like, timeline amplitudes
    f_sample    scalar like, sample frequency of the timeline

    Returns
    -------
    First: frequency bin positions (array like)
    Second: the power spectrum in the frequency bins (array like)
    """
    sample_periode = 1.0/f_sample
    spec = np.fft.fft(sig_vs_t)
    freq = np.fft.fftfreq(spec.size, d=sample_periode)
    idx = np.argsort(freq)
    freq = freq[idx]
    spec = spec[idx]
    spec = np.sqrt(np.real(spec)**2.0 + np.imag(spec)**2.0)
    return freq, spec
#-------------------------------------------------------------------------------
def sinus_vs_t(f_sample, N, f_sinus):
    """
    Sine wave amplitude vs time
    Can be used as test signal for the power spectrum analysator
    """
    t = time_slices(f_sample, N)
    return np.sin(t*f_sinus*(2.0*np.pi))
#-------------------------------------------------------------------------------
def approximate_ac_coupling(sig_vs_t):
    """
    Applys a poor man's AC coupling to the signal timeline. 
    It approximates the signal's baseline shift but neglects the 
    causal order of the pulses. Since there are no DC currents on long time
    scales, it enforces the average signal over a long periode of time to be 
    zero.
    """
    sig_vs_t -= np.mean(sig_vs_t)
#-------------------------------------------------------------------------------
def sipm_vs_t(f_sample, N, t_offset):
    """
    The FACT SIPM pulse amplitude vs time
    """
    t = time_slices(f_sample, N)

    # time line in ns
    t = 1e9*(t-t_offset)

    # evaluate template, here the equation is for nano seconds
    s_vs_t = 1.626*(1.0-np.exp(-0.3803*t))*np.exp(-0.0649*t)
    
    # Since this is only a polynomial approx. 
    # We truncate artefacts like negative amplitudes
    s_vs_t[s_vs_t < 0.0] = 0.0
    return s_vs_t
#-------------------------------------------------------------------------------
def add_first_to_second_at(f1, f2, injection_slices):
    """
    Adds the first 1D array to the second 1D array at all injection 
    slices of the third 1D array.
    """
    for injection_slice in injection_slices:
        # injection point exceeds range of f2
        if injection_slice > f2.shape[0]:
            continue

        if injection_slice < 0:
            injection_slice = 0

        # endpoint of injection in f2: e2
        e2 = injection_slice + f1.shape[0]

        # naive endpoint of sampling in f1
        e1 = f1.shape[0]

        # e2 is limited to range of f2
        if e2 > f2.shape[0]:
            e2 = f2.shape[0]

        # correct sampling range in f1 if needed
        if e2-injection_slice < f1.shape[0]:
            e1 = e2-injection_slice

        f2[injection_slice:e2] += f1[0:e1]
#-------------------------------------------------------------------------------
def white_noise(N, sigma):
    """
    white gaussian noise amplitudes
    """
    if sigma == 0:
        return np.zeros(N)
    return np.random.normal(loc=0.0, scale=sigma, size=(N))
#-------------------------------------------------------------------------------
def poisson_arrival_times(exposure_time, f):
    """
    poisson distributed arrival times of pulses in a given exposure time 
    exposure_time with an average frequency of f
    """
    arrival_times = []
    time = 0
    while time < exposure_time:
        time_until_next_arrival = random.expovariate(f)
        time += time_until_next_arrival
        if time < exposure_time:
            arrival_times.append(time)

    return np.array(arrival_times)
#-------------------------------------------------------------------------------
def fact_sig_vs_t(cfg):
    arrival_times = poisson_arrival_times(cfg['T_sample']*cfg['psc_N'], cfg['f_photons'])
    arrival_slices = np.floor(arrival_times*cfg['f_sample']).astype('int')

    mctruth = {}
    mctruth['pulse_injection_slices'] = arrival_slices

    psc_vs_t = np.zeros(cfg['psc_N'])

    add_first_to_second_at(
        sipm_vs_t(cfg['f_sample'], 300, 0.0),
        psc_vs_t, 
        mctruth['pulse_injection_slices']
    )

    approximate_ac_coupling(psc_vs_t)
    psc_vs_t = psc_vs_t + white_noise(cfg['psc_N'], cfg['std_dev_el_noise'])

    mctruth['pulse_injection_slices'] = mctruth['pulse_injection_slices']-cfg['roi_start']
    return psc_vs_t[cfg['roi_start']: cfg['roi_start']+cfg['roi_N']], mctruth

#-------------------------------------------------------------------------------
def plot_timeline_with_mc_truth(f_sample, s_vs_t_and_mc):
    s_vs_t = s_vs_t_and_mc[0]
    mc = s_vs_t_and_mc[1]
    times = 1e9*time_slices(f_sample, s_vs_t.shape[0])

    ax1 = plt.subplot(4,1,1)
    ax1.step(times, s_vs_t)
    ax1.set_xlabel('t[ns]')
    ax1.set_ylabel('A[1]')

    ax2 = plt.subplot(4,1,2, sharex=ax1)
    for s in mc['pulse_injection_slices']:
        if s < 0:
            continue
        ax2.plot([times[s], times[s]],[0, 1], 'r')

    ax2.set_xlabel('t[ns]')
    ax2.set_ylabel('MC truth')

    ax3 = plt.subplot(4,1,3)
    ax3.set_xlabel('t[ns]')
    ax3.set_ylabel('convolve')
    sipm = sipm_vs_t(f_sample, 20, 0.0)
    fcp = np.convolve(s_vs_t, sipm, mode='same')/sum(sipm)
    ax3.plot(times, fcp-fcp.min())

    ax4 = plt.subplot(4,1,4)
    frec, spec = power_spectrum(s_vs_t, f_sample)
    ax4.step(frec, spec)
    ax4.set_xlabel('f[Hz]')
    ax4.set_ylabel('I[1]')
    ax4.set_xscale('log')

    plt.show()

#-------------------------------------------------------------------------------
def extraction(sig_vs_t, puls_template, subs_pulse_template):
    sig_vs_t_copy = sig_vs_t.copy()

    arrivalSlices = []

    puls_template_integral = sum(puls_template)

    while True:
        # convolve timeline with pulse template
        sig_conv_sipm = np.convolve(sig_vs_t_copy, puls_template, mode='valid')/puls_template_integral

        # find slice with max response
        offset_slices = 5   # Seems to be needed (at least it helps) because of 
                            # the asymetric nature of the pluse template
        max_slice = int(np.round(np.argmax(sig_conv_sipm) - offset_slices))
        max_response = np.max(sig_conv_sipm)

        if max_response >= 0.45:
            # substract this pulse
            weight = 1.0 # Maybe even substracting more than one photon? 
                         # e.g.: max_photon_equivalent = np.round(max_response)
            
            #print('substract '+str(weight)+' at '+str(np.round(max_slice*cfg['T_sample']*1e9,1))+'ns')
            #plot_timeline_with_mc_truth(cfg['f_sample'], [sig_vs_t_copy, mc_truth])
            
            # substract pulse
            add_first_to_second_at(subs_pulse_template, sig_vs_t_copy, [max_slice])

            # again apply the ac coupling to avoid drift of baseline
            # the new substracted timeline is now again a valid FACT ac coupled timeline
            approximate_ac_coupling(sig_vs_t_copy)  
            
            # store the result
            arrivalSlices.append(max_slice)
        else:
            #plot_timeline_with_mc_truth(cfg['f_sample'], [sig_vs_t_copy, mc_truth])
            break

    arrivalSlices = np.array(arrivalSlices)
    arrivalSlices = arrivalSlices[arrivalSlices > 0]
    return arrivalSlices

def benchmark(arrivalsExtracted, arrivalsTruth, windowRadius=10):

    arrivalsExtracted = np.sort(arrivalsExtracted)
    arrivalsTruth = np.sort(arrivalsTruth)

    def find_nearest(array, value):
        return (np.abs(array-value)).argmin()

    bench = Bench()

    arrivalsExtractedRemaining = arrivalsExtracted.copy()

    for arrivalTruth in arrivalsTruth:

        if arrivalsExtractedRemaining.shape[0] == 0:
            bench.falseNegative += 1
        else:
            match = find_nearest(arrivalsExtractedRemaining, arrivalTruth)
            distance = np.abs(arrivalsExtractedRemaining[match] - arrivalTruth)
            if distance < windowRadius:
                arrivalsExtractedRemaining = np.delete(arrivalsExtractedRemaining, match) 
                bench.truePositive += 1
            else:
                bench.falseNegative += 1

    bench.falsePositive += arrivalsExtractedRemaining.shape[0]

    return bench

#-------------------------------------------------------------------------------
# 
# Welcome to the FACT single photon pulse extraction sandbox
#
# 1) SETUP
# --------
cfg = {}
cfg['f_sample'] = 2e9 
cfg['roi_N'] = 300 #roi: region of interest
cfg['psc_overhead'] = 3 #psc: pseudo continuos timeline
cfg['f_photons'] = 5e7 # average arrival frequency of photons (poisson distributed)
cfg['std_dev_el_noise'] = 0.0 # electronic noise amplitude in std dev of pulse hights 

cfg['T_sample'] = 1.0/cfg['f_sample'] 
cfg['roi_start'] = cfg['psc_overhead']*cfg['roi_N']
cfg['psc_N'] = (cfg['psc_overhead']+1)*cfg['roi_N']

# 2) PULS TEMPLATE
# ----------------
# pulse template of the puls to be extracted
# We do not use the full puls but only its rising edge and peak. 
# We leave out the tail
puls_template = sipm_vs_t(cfg['f_sample'], N=20, t_offset=0.0)

# 3) SUBSTRACTION PULS TEMPLATE
# -----------------------------
subs_pulse_template = -1.0*sipm_vs_t(cfg['f_sample'], N=300, t_offset=0.0)

maxWindowRadius = 10
windowRadii = np.linspace(0,maxWindowRadius,maxWindowRadius, endpoint=False)
trueFindings = np.zeros(maxWindowRadius)
falseFindings = np.zeros(maxWindowRadius)

for s, windowRadius in enumerate(windowRadii):
    
    bench = Bench()
    for i in tqdm(range(5000)):
        sig_vs_t , mc_truth = fact_sig_vs_t(cfg)

        arrivalSlicesTruth = mc_truth['pulse_injection_slices'][mc_truth['pulse_injection_slices']>=0]
        arrivalSlices = extraction(sig_vs_t, puls_template, subs_pulse_template)

        arrivalSlices = np.sort(arrivalSlices)
        arrivalSlicesTruth = np.sort(arrivalSlicesTruth)

        arrivalSlices += 2

        arrivalSlices=arrivalSlices[arrivalSlices>25]
        arrivalSlices=arrivalSlices[arrivalSlices<275]

        arrivalSlicesTruth=arrivalSlicesTruth[arrivalSlicesTruth>25]
        arrivalSlicesTruth=arrivalSlicesTruth[arrivalSlicesTruth<275]

        b = benchmark(
            arrivalSlices,
            arrivalSlicesTruth, 
            windowRadius=windowRadius)

        bench.truePositive += b.truePositive
        bench.falsePositive += b.falsePositive
        bench.falseNegative += b.falseNegative

    trueFindings[s] = bench.truePositiveRate()
    falseFindings[s] = bench.falseNegativeRate()

plt.step(windowRadii/2, falseFindings, color='g', linewidth=5.0, label='false negative (Miss Rate)')
plt.step(windowRadii/2, trueFindings, color='b', linewidth=5.0, label='true positive (Sensitivity)')
plt.ylabel('rate [1]')
plt.xlabel('matching window radius [ns]')
plt.legend(bbox_to_anchor=(0., 1.02, 1., .102), loc=3,
           ncol=2, mode="expand", borderaxespad=0.)