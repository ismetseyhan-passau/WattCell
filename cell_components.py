# -*- coding: utf-8 -*-
'''
Created on 27/07/2024

@author: Marcin Orzech
'''

from dataclasses import dataclass, field
from typing import Dict, Any

materials = {
    'Cu': {'density': 8.94, 'thickness': 6},  # thickness in um
    'Al': {'density': 2.7, 'thickness': 16},  # thickness in um
    'Prussian Blue': {
        'density': 1.8,  # in g/cm3
        'capacity': 150,  # in Ah/kg
        'voltage': 3.2  # in V
    },
    'Hard Carbon': {
        'capacity': 300,
        'voltage': 0.1,
        'density': 1.6
    },
    'SuperP': {'density': 1.9},
    'PVDF': {'density': 1.78},
    'CMC+SBR': {'density': (1.6+0.96)/2},
    'Celgard 2325': {
        'thickness': 25,  # in um
        'porosity': 0.41,
        'density': 0.74  # in g/cm³ from https://core.ac.uk/download/pdf/288499223.pdf
    },
    'pouch': {
        'thickness': 113,  # in um
        'density': 1.62,  # in g/cm³
        'extra_width': 0.9,  # in cm
        'extra_height': 2  # in cm
    },
    'tabs': {
        'Al': {
            'density': 2.7
        }
    },
    'electrolytes': {
        'NaPF6 in diglyme': {
            'density': 1.15
        }
    }
}

@dataclass
class Electrode:
    active_material: str
    mass_ratio: Dict[str, float]
    binder: str
    porosity: float
    voltage: float  # V
    capacity: float  # Ah/kg
    density_am: float  # g/cm3
    width: float  # cm
    height: float  # cm
    cc_thickness: float  # cm
    current_collector: str
    thickness: float = 0 # cm
    tab_height: float = 1  # cm
    tab_width: float = 1  # cm
    density: float = field(init=False)
    areal_capacity: float = field(init=False)  # mAh/cm²

    def __post_init__(self):
        self.calculate_composite_density()
        self.calculate_areal_capacity()

    def calculate_composite_density(self):
        volumes = {
            'am': self.mass_ratio['am'] / self.density_am,
            'carbon': self.mass_ratio['carbon'] / materials['SuperP']['density'],
            'binder': self.mass_ratio['binder'] / materials[self.binder]['density']
        }
        volume_ratios = {k: v / sum(volumes.values()) for k, v in volumes.items()}
        self.density = (1 - self.porosity) * (
            volume_ratios['am'] * self.density_am +
            volume_ratios['carbon'] * materials['SuperP']['density'] +
            volume_ratios['binder'] * materials[self.binder]['density']
        )

    def calculate_areal_capacity(self):
        self.areal_capacity = self.density * self.thickness * self.capacity * self.mass_ratio['am']

@dataclass
class Separator:
    material: str
    width: float  # cm
    height: float  # cm
    thickness: float  # cm
    porosity: float
    density: float

@dataclass
class Electrolyte:
    material: str
    density: float
    volume_excess: float = 0
    volume: float = field(init=False)
    volume_per_ah: float = field(init=False)
@dataclass
class Pouch:
    width: float  # cm
    height: float  # cm
    thickness: float  # cm
    density: float

@dataclass
class Tab:
    material_cathode: str
    material_anode: str
    height: float  # cm
    width: float  # cm
    thickness: float # cm
    density_cathode: float = field(init=False)
    density_anode: float = field(init=False)

    def __post_init__(self):
        self.density_cathode = materials.get(self.material_cathode)['density']
        self.density_anode = materials.get(self.material_anode)['density']


@dataclass
class Cell:
    cathode: Electrode
    anode: Electrode
    separator: Separator
    electrolyte: Electrolyte
    format: Pouch
    tabs: Tab
    layers_number: int
    n_p_ratio: float
    ice: float = 0.93
    
    # attributes to store calculation results
    volumetric_energy_density: float = field(init=False)
    gravimetric_energy_density: float = field(init=False)
    energy: float = field(init=False)
    capacity: float = field(init=False)
    total_mass: float = field(init=False)
    total_volume: float = field(init=False)


    def __post_init__(self):
        self.calculate_anode_properties()
        self.calculate_energy_density()

    def calculate_anode_properties(self):
        required_anode_capacity = self.cathode.areal_capacity * self.n_p_ratio
        
        # Calculate required anode thickness
        self.anode.thickness = required_anode_capacity / (
            self.anode.density * self.anode.capacity * self.anode.mass_ratio['am'])
        
        # Recalculate anode areal capacity
        self.anode.calculate_areal_capacity()

    def calculate_energy_density(self):
        '''
        calculation of final values inputs
        results:
        total mass
        total volume
        capacity
        energy
        specific energy
        energy density
        '''
        # Calculate volumes of individual item (cm3) 
        cathode_volume = self.cathode.width * self.cathode.height * self.cathode.thickness* 2 * self.layers_number
        anode_volume = self.anode.width * self.anode.height * self.anode.thickness * (2 * self.layers_number + 2)  # Extra anode layer
        separator_volume = self.separator.width * self.separator.height * self.separator.thickness * 2 * self.layers_number
        pouch_volume = self.format.width * self.format.height * self.format.thickness * 2
        anode_cc_volume = (self.layers_number + 1)* (  # Extra anode current collector
            self.anode.width * self.anode.height + self.anode.tab_height + self.anode.tab_width
            ) * self.anode.cc_thickness
        cathode_cc_volume = self.layers_number * (
            self.cathode.width * self.cathode.height + self.cathode.tab_height * self.cathode.tab_width
            ) * self.cathode.cc_thickness

        # Calculate masses (g)
        cathode_mass = cathode_volume * self.cathode.density
        anode_mass = anode_volume * self.anode.density
        separator_mass = separator_volume * self.separator.density
        pouch_mass = pouch_volume * self.format.density
        cathode_cc_mass = cathode_cc_volume * materials[self.cathode.current_collector]['density']
        anode_cc_mass = anode_cc_volume * materials[self.anode.current_collector]['density']
        tabs_mass = self.tabs.height * self.tabs.width * self.tabs.thickness * (self.tabs.density_cathode + self.tabs.density_anode)

        # Calculate void volume for electrolyte
        cathode_void_volume = cathode_volume * self.cathode.porosity
        anode_void_volume = anode_volume * self.anode.porosity
        separator_void_volume = separator_volume * self.separator.porosity
        total_void_volume = cathode_void_volume + anode_void_volume + separator_void_volume

        # Calculate electrolyte mass and volume
        self.electrolyte.volume = total_void_volume * (1 + self.electrolyte.volume_excess)
        electrolyte_mass = self.electrolyte.volume * self.electrolyte.density

        # Calculate total mass and volume
        self.total_mass = cathode_mass + cathode_cc_mass + anode_mass + anode_cc_mass + separator_mass + pouch_mass + tabs_mass + electrolyte_mass
        self.total_volume = cathode_volume + anode_volume + separator_volume + pouch_volume + (self.electrolyte.volume - total_void_volume) + anode_cc_volume + cathode_cc_volume

        # Calculate capacity (based on the limiting electrode)
        cathode_capacity = cathode_mass * self.cathode.mass_ratio['am'] * self.cathode.capacity / 1000  # Convert to Ah
        anode_capacity = anode_mass * self.anode.mass_ratio['am'] * self.anode.capacity / 1000  # Convert to Ah
        self.capacity = min(cathode_capacity, anode_capacity) * self.ice

        # Calculate volume of electrolyte per Ah
        self.electrolyte.volume_per_ah = self.electrolyte.volume / self.capacity  # cm³/Ah

        # Calculate energy
        cell_voltage = self.cathode.voltage - self.anode.voltage
        self.energy = self.capacity * cell_voltage  # in Wh

        # Calculate energy density and specific energy
        self.volumetric_energy_density = self.energy / self.total_volume * 1000  # Wh/L
        self.gravimetric_energy_density = self.energy / self.total_mass * 1000  # Wh/kg
