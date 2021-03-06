#!/usr/bin/env python
#
# Creates solar absorption and continuum files tuned for a specific instrument using generic data of solar lines and 
# and continuum from SOLSPEC

import os
import sys
import logging

import numpy as np
import h5py

from refractor import framework as rf
from refractor.factory import process_config

INPUT_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), "../../input/common/input/"))

SOLAR_LINE_LIST = os.path.join(INPUT_PATH, 'solar_merged.108')
SOLAR_CONTINUUM_SOLSPEC_INPUT = os.path.join(INPUT_PATH, "solspec.composite.atl1_1.txt")
SOLAR_CONTINUUM_PARAM_INPUT = os.path.join(INPUT_PATH, 'solar_continuum_params.h5')

from scipy.constants import speed_of_light, h as planck

logger = logging.getLogger()

class SolarTablesFile(object):

    "Creates solar table data for a configuration"

    continuum_methods = {
        "param": "_compute_solar_continuum_from_param",
        "solspec": "_compute_solar_continuum_from_solspec",
        "planck": "_compute_solar_continuum_from_planck",
    }

    def __init__(self, config_filename, padding=150, grid_spacing=0.001, compute_absorption=True, continuum_method="solspec"):

        # Padding on either side of grid to use, in wavenumbers
        self.padding = padding

        # Grid spacing in wavenumbers
        self.grid_spacing = grid_spacing

        # Initialize data arrays
        self.chan_grids = []

        self.compute_absorption = compute_absorption

        if continuum_method is not None and continuum_method not in self.continuum_methods.keys():
            raise Exception("Unrecognized continuum method: %s, must be one of: %s" % (continuum_method, self.continuum_methods.keys))

        if continuum_method is not None:
            self.continuum_func = getattr(self, self.continuum_methods[continuum_method])
        else:
            self.continuum_func = None

        self._load_from_config(config_filename)
 
    def _load_from_config(self, config_filename):

        logging.debug("Loading config from: %s" % config_filename)

        self._load_config(config_filename)
        self._grids_from_spec_win(self.config_inst['spec_win'])

        if self.compute_absorption:
            self._compute_solar_absorption()

        if self.continuum_func is not None:
            self.continuum_func()

    def _load_config(self, config_filename):

        glb_vars = globals().copy()
        glb_vars["__file__"] = config_filename
        glb_vars["__name__"] = None

        exec(open(config_filename, "r").read(), glb_vars)

        config_def = glb_vars['config_def']

        # Disable solar usage
        if 'solar_model' in config_def['forward_model']['spectrum_effect']['effects']:
            config_def['forward_model']['spectrum_effect']['effects'].remove('solar_model')

        self.config_inst = process_config(config_def)

    def _grids_from_spec_win(self, spec_win):
        # Get spectral windows as wavenumbers
        spec_win_wn = spec_win.range_array.convert_wave("cm^-1").value

        self.chan_grids = []
        for chan_idx in range(spec_win_wn.shape[0]):
            chan_range = sorted(spec_win_wn[chan_idx, 0, :])
            chan_points = np.arange(chan_range[0]-self.padding, chan_range[1]+self.grid_spacing+self.padding, self.grid_spacing)
            self.chan_grids.append(chan_points)

    def _compute_solar_absorption(self):
        logging.debug("Computing solar absorption")

        # Create solar absorption
        solar_abs_calc = rf.SolarAbsorptionGfitFile(SOLAR_LINE_LIST, 1.0)

        self.solar_abs = []
        self.abs_wavenumbers = []
        for chan_points in self.chan_grids:
            chan_abs = solar_abs_calc.solar_absorption_spectrum(rf.SpectralDomain(chan_points)).value
            self.solar_abs.append(chan_abs)
            self.abs_wavenumbers.append(chan_points)

    def _compute_solar_continuum_from_param(self):
        logging.debug("Computing solar continuum")

        cont_inp_data = rf.HdfFile(SOLAR_CONTINUUM_PARAM_INPUT)
        cont_coeffs = cont_inp_data.read_double_with_unit_1d("continuum_coeffs")
        solar_cont_poly = rf.SolarContinuumPolynomial(cont_coeffs, False)

        self.solar_continuum = []
        self.cont_wavenumbers = []
        for chan_points in self.chan_grids:
            chan_cont = solar_cont_poly.solar_continuum_spectrum(rf.SpectralDomain(chan_points)).value
            # Reverse to increasing wn order
            self.solar_continuum.append(chan_cont)
            self.cont_wavenumbers.append(chan_points)

    def _compute_solar_continuum_from_solspec(self):
        logging.debug("Computing solar continuum")

        solspec_data = np.loadtxt(SOLAR_CONTINUUM_SOLSPEC_INPUT)
        alpha = rf.DoubleWithUnit(speed_of_light * planck, rf.Unit("m s^-1 J s"))
        output_units = rf.Unit("(mW / cm^-1) / (ph / s / micron)")

        # Convert nm to wavenumbers and reverse
        # Input units = "mW / cm^2 / sr / nm"
        solspec_grid = rf.ArrayWithUnit_double_1(solspec_data[::-1, 0], "nm")
        solspec_cont = rf.ArrayWithUnit_double_1(solspec_data[::-1, 1], "mW / cm^2 / sr / nm")

        solspec_wn = solspec_grid.convert_wave("cm^-1").value

        convert_fac = rf.ArrayWithUnit_double_1()
        convert_fac.value = alpha.value / solspec_grid.value
        convert_fac.units = alpha.units / rf.Unit("cm^-1") / rf.Unit("ph")
        convert_fac = convert_fac.convert(output_units)

        # Converts to ph / s / m^2 / sr / um
        cont_output = rf.ArrayWithUnit_double_1()
        cont_output.value = solspec_cont.value / convert_fac.value
        cont_output.units = solspec_cont.units / convert_fac.units

        self.solar_continuum = []
        self.cont_wavenumbers = []
        for chan_points in self.chan_grids:
            where_chan = np.where(np.logical_and(solspec_wn >= chan_points[0], solspec_wn <= chan_points[-1]))
            
            chan_poly = np.polyfit(solspec_wn[where_chan], cont_output.value[where_chan], 3)
            chan_cont = np.poly1d(chan_poly)(solspec_wn[where_chan][::10])
            
            # Reverse to increasing wn order
            self.solar_continuum.append(chan_cont)
            self.cont_wavenumbers.append(solspec_wn[where_chan][::10])

    def _compute_solar_continuum_from_planck(self):
        pass

    def write(self, solar_table_filename):
        logging.debug("Writing solar model data to: %s" % solar_table_filename)

        output = h5py.File(solar_table_filename, 'w')

        # Create absorption datasets
        for idx, (chan_wn, chan_abs) in enumerate(zip(self.abs_wavenumbers, self.solar_abs)):
            wn_name = "/Solar/Absorption/Absorption_%d/wavenumber" % (idx + 1)
            wn_ds = output.create_dataset(wn_name, data=chan_wn)
            wn_ds.attrs['Units'] = "cm^-1"
            wn_ds.attrs['Frame'] = "Solar rest frame"
            
            abs_name = "/Solar/Absorption/Absorption_%d/spectrum" % (idx + 1)
            abs_ds = output.create_dataset(abs_name, data=chan_abs)
            abs_ds.attrs['Units'] = "dimensionless"
            
            
        for idx, (chan_wn, chan_cont) in enumerate(zip(self.cont_wavenumbers, self.solar_continuum)):
            wn_name = "/Solar/Continuum/Continuum_%d/wavenumber" % (idx + 1)
            wn_ds = output.create_dataset(wn_name, data=chan_wn)
            wn_ds.attrs['Units'] = "cm^-1"
            
            abs_name = "/Solar/Continuum/Continuum_%d/spectrum" % (idx + 1)
            cont_ds = output.create_dataset(abs_name, data=chan_cont)
            cont_ds.attrs['Units'] = "ph / s / m^2 / micron"
            
        output.close()

def main():

    from argparse import ArgumentParser
    
    parser = ArgumentParser(description="Creates a solar tables HDF5 file from a ReFRACtor Python config file")

    parser.add_argument("config_filename",
        help="ReFRACtor factory based Python config file, expects to find 'config_def' variable to process")

    parser.add_argument("--output_filename", "-o", metavar="FILENAME", default="solar_model.h5",
        help="Filename of output solar model tables")

    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)

    solar_tab_file = SolarTablesFile(args.config_filename)
    solar_tab_file.write(args.output_filename)


if __name__ == "__main__":
    main()
