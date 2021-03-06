import numpy as np

from .base import Creator
from .. import param

from refractor import framework as rf

class PerChannelMixin(object):

    num_channels = param.Scalar(int)

    def check_num_channels(self, check_num):
        "Issue a warning when the number of channels in some data source does not match the expected number"

        if not self.num_channels() == check_num:
            raise param.ParamError("Number of channels for data source: %d does not match expected number: %d" % (check_num, self.num_channels()))

class SpectralWindowRange(Creator):
    
    window_ranges = param.ArrayWithUnit(dims=3)
    bad_sample_mask = param.Array(dims=2, required=False)
    
    def create(self, **kwargs):

        win_ranges = self.window_ranges()
        bad_sample_mask = self.bad_sample_mask()

        if bad_sample_mask is not None:
            return rf.SpectralWindowRange(win_ranges, bad_sample_mask)
        else:
            return rf.SpectralWindowRange(win_ranges)

class SpectrumSamplingBase(Creator, PerChannelMixin):

    high_res_spacing = param.Choice(param.ArrayWithUnit(dims=1), param.DoubleWithUnit())

    def spacing(self):
        "Returns the array with unit value for spacing specified regardless if it was specified as an array or scalar value with unit"

        spacing_val = self.high_res_spacing()
        num_channels = self.num_channels()

        if isinstance(spacing_val, rf.DoubleWithUnit):
            # Create an ArrayWithDouble matching the number of channels used
            spacing_used = rf.ArrayWithUnit_double_1(np.full(num_channels, spacing_val.value), spacing_val.units)
        else:
            self.check_num_channels(spacing_val.value.shape[0])
            spacing_used = spacing_val

        return spacing_used

class FixedSpacingSpectrumSampling(SpectrumSamplingBase):

    def create(self, **kwargs):
        return rf.SpectrumSamplingFixedSpacing(self.spacing())

class UniformSpectrumSampling(SpectrumSamplingBase):

    def create(self, **kwargs):
        return rf.UniformSpectrumSampling(self.spacing())

class NonuniformSpectrumSampling(SpectrumSamplingBase):

    channel_domains = param.Iterable()

    def create(self, **kwargs):
        domains = self.channel_domains()
        full_spec_spacing = rf.SpectrumSamplingFixedSpacing(self.spacing())

        if len(domains) != self.num_channels():
            raise param.ParamError("Number of channel domains %d does not match the number of channels %d" % (len(domains), self.num_channels()))

        for idx, dom in enumerate(domains):
            if not isinstance(dom, rf.SpectralDomain):
                raise param.ParamError("Channel domain value at index %d is not a instance of SpectralDomain" % idx)

        return rf.NonuniformSpectrumSampling(*domains, full_spec_spacing)

class SpectrumEffectList(Creator):

    effects = param.Iterable(str)
    num_channels = param.Scalar(int)

    def create(self, **kwargs):

        all_effects = []
        for effect_name in self.effects():
            self.register_parameter(effect_name, param.Iterable())
            all_effects.append(self.param(effect_name))

        # Map these into an outer vector for each channel, with an inner vector for each effect
        spec_eff = rf.vector_vector_spectrum_effect()
        for chan_index in range(self.num_channels()):
            per_channel_eff = rf.vector_spectrum_effect()

            for effect in all_effects:
                per_channel_eff.push_back(effect[chan_index])

            spec_eff.push_back(per_channel_eff)

        return spec_eff

class ForwardModel(Creator):

    instrument = param.InstanceOf(rf.Instrument)
    spec_win = param.InstanceOf(rf.SpectralWindow)
    radiative_transfer = param.InstanceOf(rf.RadiativeTransfer)
    spectrum_sampling = param.InstanceOf(rf.SpectrumSampling)
    spectrum_effect = param.ObjectVector("vector_spectrum_effect")

    def create(self, **kwargs):
        fm = rf.StandardForwardModel(self.instrument(),
                                     self.spec_win(), 
                                     self.radiative_transfer(),
                                     self.spectrum_sampling(), 
                                     self.spectrum_effect())

        fm.setup_grid()

        return fm
