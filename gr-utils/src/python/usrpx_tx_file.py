#!/usr/bin/env python
#
# Copyright 2010 Free Software Foundation, Inc.
# 
# This file is part of GNU Radio
# 
# GNU Radio is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
# 
# GNU Radio is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with GNU Radio; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.
# 

"""
Read 32-bit little-endian samples from a file and send those samples to the
USRP/USRP2.
"""

from gnuradio import gr, eng_notation
from gnuradio.blks2 import generic_usrp_sink_c
from gnuradio.eng_option import eng_option
from optparse import OptionParser
import sys

n2s = eng_notation.num_to_str

class tx_cfile_block(gr.top_block):

    def __init__(self, options, input_filename):
        gr.top_block.__init__(self)

        gr.enable_realtime_scheduling()

        if options.real:
            sizeof_input_samples = gr.sizeof_float
        else:
            sizeof_input_samples = gr.sizeof_gr_complex

        self.src = gr.file_source(sizeof_input_samples,
                                  input_filename,
                                  repeat = options.loop)
        self.u = generic_usrp_sink_c(interface = options.interface,
                                     mac_addr = options.mac_addr,
                                     subdev_spec = options.tx_subdev_spec)
        print 'Using %s' % str(self.u)
        print 'Possible tx frequency range: %s - %s' % \
            (n2s(self.u.freq_range()[0]), n2s(self.u.freq_range()[1]))

        # we need to find the closest decimation rate the USRP can handle
        # to the input file's sampling rate
        try:
            ideal_interp = self.u.dac_rate() / options.rate
            # pick the closest interpolation rate
            interp = [x for x in self.u.get_interp_rates()
                      if x <= ideal_interp][-1]
            self.u.set_interp(interp)
        except IndexError:
            sys.stderr.write('Failed to set USRP interpolation rate\n')
            raise SystemExit, 1

        output_rate = self.u.dac_rate() / interp
        resamp_ratio = output_rate / options.rate 

        # since the input file sample rate may not be exactly what our
        # output rate of the USRP (as determined by the interpolation rate),
        # we need to resample our input to the output rate
        num_filters = 32
        cutoff = 0.99 * options.rate / 2.
        transition = 0.1 * options.rate / 2.
        resamp_taps = gr.firdes_low_pass(num_filters * 1.0,
                                         num_filters * options.rate,
                                         cutoff,
                                         transition)
        self.resamp = gr.pfb_arb_resampler_ccf(resamp_ratio,
                                               resamp_taps,
                                               num_filters)

        if options.gain is None:
            # if no gain was specified, use the mid-point in dB
            g = self.u.gain_range()
            options.gain = float(g[0]+g[1])/2
        self.u.set_gain(options.gain)

        res = self.u.set_center_freq(options.freq)
        if not res:
            sys.stderr.write('Failed to set frequency\n')
            raise SystemExit, 1

        if options.real:
            # our samples are real
            # we need to convert them to complex without a hilbert filter
            self.hilbert = gr.hilbert_fc(64)
            self.connect(self.src, self.hilbert, self.resamp, self.u)
        else:
            # our samples are complex
            self.connect(self.src, self.resamp, self.u)

def get_options():
    usage="%prog: [options] input_filename"

    parser = OptionParser(option_class=eng_option, usage=usage)

    parser.add_option("-R", "--tx-subdev-spec", type="subdev", default=None,
                      help="select USRP1 Tx side A or B (default=None)")
    parser.add_option("-e", "--interface", type="string", default=None,
                      help="specify USRP2 Ethernet interface [default=None]")
    parser.add_option("-m", "--mac-addr", type="string", default=None,
                      help="specif USRP2 MAC address [default=None]")

    parser.add_option("-f", "--freq", type="eng_float", default=None,
                      help="set frequency to FREQ", metavar="FREQ")
    parser.add_option("-g", "--gain", type="eng_float", default=None,
                      help="set gain in dB (default is midpoint)")
    parser.add_option("-r", "--rate", type="eng_float", default=None,
                      help="specify the input file sample rate [default=all]",
                      metavar="RATE")
    parser.add_option("-l", "--loop", action="store_true", default=False,
                      help="loop the input file [default=False]")

    parser.add_option("", "--real", action="store_true", default=False,
                      help="use a real file as input [default=complex]")

    (options, args) = parser.parse_args()

    if len(args) != 1:
        parser.print_help()
        raise SystemExit, 1

    if options.freq is None:
        parser.print_help()
        sys.stderr.write('You must specify the frequency\n')
        raise SystemExit, 1
    if options.rate is None:
        parser.print_help()
        sys.stderr.write('You must specify the input file sample rate\n')
        raise SystemExit, 1

    return (options, args[0])

if __name__ == '__main__':
    (options, input_filename) = get_options()
    tb = tx_cfile_block(options, input_filename)
    
    try:
        tb.run()
    except KeyboardInterrupt:
        pass
