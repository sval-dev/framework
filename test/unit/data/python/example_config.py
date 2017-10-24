import os
import h5py
import logging

import numpy as np

import refractor.factory.creator as creator
import refractor.factory.param as param
from refractor.factory import process_config
from refractor import framework as rf

logging.basicConfig(level=logging.DEBUG)

static_input_file = os.path.join(os.path.dirname(__file__), "../lua/example_static_input.h5")
static_input = h5py.File(static_input_file)
ils_file = os.path.join(os.path.dirname(__file__), "../lua/ils_data.h5")
ils_input = h5py.File(ils_file)

solar_file = os.path.join(os.path.dirname(__file__), "../../../../input/common/input/l2_solar_model.h5")

data_dir = os.path.join(os.path.dirname(__file__), '../in/common')
l1b_file = os.path.join(data_dir, "l1b_example_data.h5")
met_file = os.path.join(data_dir, "met_example_data.h5")

observation_id = "2014090915251774"

# Helpers to abstract away getting data out of the static input file
def static_value(dataset, dtype=None):
    return np.array(static_input[dataset][:], dtype=dtype)

def static_units(dataset):
    return static_input[dataset].attrs['Units'][0].decode('UTF8') 


config_def = {
    'creator': creator.base.SaveToCommon,
    'order': ['input', 'common', 'spec_win', 'spectrum_sampling', 'atmosphere', 'radiative_transfer', 'instrument', 'state_vector', 'forward_model'],
    'input': {
        'creator': creator.base.SaveToCommon,
        'l1b': rf.ExampleLevel1b(l1b_file, observation_id),
        'met': rf.ExampleMetFile(met_file, observation_id),
    },
    'common': {
        'creator': creator.base.SaveToCommon,
        'desc_band_name': static_value("Common/desc_band_name", dtype=str),
        'hdf_band_name': static_value("Common/hdf_band_name", dtype=str),
        'band_reference': {
            'creator': creator.value.ArrayWithUnit,
            'value': static_value("Common/band_reference_point"),
            'units': static_units("Common/band_reference_point"),
        },
        'num_channels': 3,
        'absco_base_path': '/mnt/data1/absco',
        'constants': {
            'creator': creator.common.DefaultConstants,
        },
        'stokes_coefficients': {
            'creator': creator.l1b.ValueFromLevel1b,
            'field': "stokes_coefficient",
        },
    },
    'spec_win': {
        'creator': creator.forward_model.SpectralWindowRange,
        'window_ranges': {
            'creator': creator.value.ArrayWithUnit,
            'value': static_value("/Spectral_Window/microwindow"),
            'units': static_units("/Spectral_Window/microwindow"),
        },
    },
    'spectrum_sampling': {
        'creator': creator.forward_model.UniformSpectrumSampling,
        'high_res_spacing': rf.DoubleWithUnit(0.01, "cm^-1"), 
    },
    'atmosphere': {
        'creator': creator.atmosphere.AtmosphereCreator,
        'pressure': {
            'creator': creator.atmosphere.PressureSigma,
            'apriori': {
                'creator': creator.met.ValueFromMet,
                'field': "surface_pressure",
            },
            'a_coeff': static_value("Pressure/Pressure_sigma_a"),
            'b_coeff': static_value("Pressure/Pressure_sigma_b"),
        },
        'temperature': {
            'creator': creator.atmosphere.TemperatureMet,
            'apriori': static_value("Temperature/Offset/a_priori")
        },
        'altitudes': { 
            'creator': creator.atmosphere.AltitudeHydrostatic,
            'latitude': {
                'creator': creator.l1b.ValueFromLevel1b,
                'field': "latitude",
            },
            'surface_height': {
                'creator': creator.l1b.ValueFromLevel1b,
                'field': "altitude",
            },
        },
        'absorber': {
            'creator': creator.atmosphere.AbsorberAbsco,
            'gases': ['CO2'],
            'CO2': {
                'creator': creator.atmosphere.AbsorberGasDefinition,
                'vmr': {
                    'creator': creator.atmosphere.AbsorberVmrLevel,
                    'apriori': {
                        'creator': creator.atmosphere.GasVmrApriori,
                        'gas_name': 'CO2',
                        'reference_atm_file': static_input_file,
                    },
                },
                'absorption': {
                    'creator': creator.atmosphere.AbscoHdf,
                    'table_scale': [1.0, 1.0, 1.004],
                    'filename': "v5.0.0/co2_devi2015_wco2scale-nist_sco2scale-unity.h5",
                },
            },
            'H2O': {
            },
            'O2': {
            },
        },
        'relative_humidity': {
            'creator': creator.atmosphere.RelativeHumidity,
        },
        'ground': {
            'creator': creator.base.PickChild,
            'child': 'lambertian',
            'lambertian': {
                'creator': creator.ground.GroundLambertian,
                'apriori': {
                    'creator': creator.ground.AlbedoFromSignalLevel,
                    'signal_level': {
                        'creator': creator.l1b.ValueFromLevel1b,
                        'field': "signal",
                    },
                    'solar_zenith': {
                        'creator': creator.l1b.ValueFromLevel1b,
                        'field': "solar_zenith",
                    },
                    'solar_strength': np.array([4.87e21, 2.096e21, 1.15e21]),
                    'solar_distance': {
                        'creator': creator.l1b.SolarDistanceFromL1b,
                    },
                },
            },
        },
    },
    'radiative_transfer': {
        'creator': creator.rt.LidortRt,
        'solar_zenith': {
            'creator': creator.l1b.ValueFromLevel1b,
            'field': "solar_zenith",
        },
        'observation_zenith': {
            'creator': creator.l1b.ValueFromLevel1b,
            'field': "sounding_zenith",
        },
        'observation_azimuth': {
            'creator': creator.l1b.ValueFromLevel1b,
            'field': "sounding_azimuth",
        },
        'num_streams': 4,
        'num_mom': 16,
    },
    'instrument': {
        'creator': creator.instrument.IlsInstrument,
        'ils_half_width': {
            'creator': creator.value.ArrayWithUnit,
            'value': np.array([4.09e-04, 1.08e-03, 1.40e-03]),
            'units': "um",
        },
        'dispersion': {
            'creator': creator.instrument.DispersionPolynomial,
            'apriori': {
                'creator': creator.l1b.ValueFromLevel1b,
                'field': 'spectral_coefficient',
            },
            'number_samples': static_value("Instrument/Dispersion/number_pixel"),
            'is_one_based': True,
            'num_parameters': 2,
        },
        'ils_function': {
            'creator': creator.instrument.IlsTable,
            'delta_lambda': ils_input["/InstrumentData/ils_delta_lambda"][:],
            'response': ils_input["/InstrumentData/ils_relative_response"][:],
        },
        'instrument_correction': {
            'creator': creator.instrument.InstrumentCorrectionList,
            'corrections': [],
        },
    },
    'state_vector': {
        'creator': creator.state_vector.StateVector,
    },
    'forward_model': {
        'creator': creator.forward_model.ForwardModel,
        'spectrum_effect': {
            'creator': creator.forward_model.SpectrumEffectList,
            'effects': ["solar_model",],
            'solar_model': {
                'creator': creator.solar_model.SolarAbsorptionAndContinuum,
                'doppler': {
                    'creator': creator.solar_model.SolarDopplerShiftPolynomial,
                    'time': {
                        'creator': creator.l1b.ValueFromLevel1b,
                        'field': "time",
                    },
                    'latitude': {
                        'creator': creator.l1b.ValueFromLevel1b,
                        'field': "latitude",
                    },
                    'solar_zenith': {
                        'creator': creator.l1b.ValueFromLevel1b,
                        'field': "solar_zenith",
                    },
                    'solar_azimuth': {
                        'creator': creator.l1b.ValueFromLevel1b,
                        'field': "solar_azimuth",
                    },
                    'altitude': {
                        'creator': creator.l1b.ValueFromLevel1b,
                        'field': "altitude",
                    },
                },
                'absorption': {
                    'creator': creator.solar_model.SolarAbsorptionTable,
                    'solar_data_file': solar_file,
                },
                'continuum': {
                    'creator': creator.solar_model.SolarContinuumTable,
                    'solar_data_file': solar_file,
                },
            },
        },
    },
}

if __name__ == "__main__":
    config_inst = process_config(config_def)

    from pprint import pprint
    pprint(config_inst, indent=4)

