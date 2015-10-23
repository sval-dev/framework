------------------------------------------------------------
--- Note that the use of base_config.lua is entirely optional.
--- There is a small number of global variables that you
--- need to create, you can do this however you want.
---
--- The variables are:
--- logger - A LogImp
--- forward_model - A ForwardModel
--- solver - A ConnorSolver
--- initial_guess - A InitialGuess
--- number_pressure_level - Integer giving the number of pressure 
---    levels. This is used to size the output file, so it should
---    be the maximim pressure
--- number_aerosol - Integer giving number of Aerosol particles. 
---    Can be 0. This is used to size the output file.
--- number_band - Integer giving number of spectral bands.
--- iteration_output - Boolean. True if we should write out iteration
---   output
--- register_output - A VectorRegisterOutput giving the
---   list of output that should be generated. This list can empty if
---   no output is desired.
------------------------------------------------------------

require "oco_base_config"

config = OcoBaseConfig:new()

config.sid_string = "2014101812360378"

config.spectrum_file = "../input/oco2_L1bScTG_01576a_141018_B5000x4_150210000451s_spliced.h5"
config.imap_file = "../input/oco2_L2IDPTG_01576a_141018_B5000x4_150210002838s_spliced.h5"
config.ecmwf_file = "../input/oco2_ECMWFTG_01576a_141018_B5000x4_150210001017s_spliced.h5"

-- Additional functions used by rmgr snippets
require "helper_functions"

-- Change convergence values
config.solver.max_iteration=10
config.solver.max_divergence=5
config.solver.gamma_initial=100.0

-- Use BRDF Soil Ground
use_brdf = DispatchCreator:new()

function use_brdf:get_creator()
    return ConfigCommon.ground_brdf_soil
end

config.fm.atmosphere.ground.creator = use_brdf

-- Effectively disable Rahman Factor, Asymmetry Factor, Breon Factor
function cov_ampl_geom(orig_cov_func)
    return function(self, i)
        local cov = orig_cov_func(self, i)
        cov:set(0,0, 1e-20)
        cov:set(2,2, 1e-20)
        cov:set(3,3, 1e-20)
        cov:set(5,5, 1e-20)
        return cov
    end
end

config.fm.atmosphere.ground.brdf_soil.covariance = cov_ampl_geom(config.fm.atmosphere.ground.brdf_soil.covariance)
config.fm.atmosphere.ground.brdf_veg.covariance = cov_ampl_geom(config.fm.atmosphere.ground.brdf_veg.covariance)

config:do_config()
