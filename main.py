from subprocess import Popen, PIPE, call
from ngspice_read import ngspice_read
import tempfile
import os
import re
import json

def run_spice(spice):
    raw_file = os.path.join(tempfile.mkdtemp(), "spice.raw")
    Popen(['ngspice', '-a', '-b', '-r' + raw_file], stdin=PIPE, stdout=PIPE).communicate(input=spice.encode())
    return ngspice_read(raw_file)

def connect(*args):
    node = None 
    circuit = None
    for arg in args:
        if isinstance(arg, Port):
            if node is None:
                circuit = arg.circuit
                node = arg.circuit.node_count
            arg.node = node
        else:
            for port in arg.ports:
                if node is None:
                    circuit = port.circuit
                    node = port.circuit.node_count
                if port.node is None:
                    port.node = node
                    break
    if len(args) == 2:
        first = args[0]
        if isinstance(first, Port):
            first = first.component
        second = args[1]
        if isinstance(second, Port):
            second = second.component
    else:
        pass
    circuit.node_count += 1
    return Port(circuit, node=node)

GROUND = 'gnd'

def ground(*args):
    for arg in args:
        if isinstance(arg, Port):
            arg.node = 0
        else:
            for port in arg.ports:
                if port.node is None:
                    port.node = 0
                    break

class Port(object):
    def __init__(self, circuit, component=None, node=None, name=None):
        self.circuit = circuit
        self.node = node
        self.component = component
        self.name = name

    @property
    def voltage(self):
        return self.circuit.operating_points[self.node]

class Component(object):
    def __init__(self, prefix=None, name=None):
        pass

class Circuit(object):
    def __init__(self):
        self.node_count = 1 # 0 is allocated to GND
        self.components = []
        self.operating_points = {}

    def add(self, component):
        self.components.append(component)

    def generate_spice(self):
        spice = ""
        for component in self.components:
            spice += component.generate_spice() + "\n"
        return spice

    def render_svg(self):
        cells = { component.name: component.json() for component in self.components }
        cells['gnd'] = {
            'type': 'gnd',
            'port_directions': {
                'A': 'input'
            },
            'connections': {
                'A': [0]
            }
        }
        netlist = {'modules': {
            'circuit': {
                'cells': cells }}}

        scratch_dir = tempfile.mkdtemp()
        netlist_path = os.path.join(scratch_dir, "netlist.json")
        circuit = os.path.join(scratch_dir, "circuit.svg")
        with open(netlist_path,'w') as f:
            f.write(json.dumps(netlist))
        call(['netlistsvg', netlist_path, '--skin', 'analog.svg', '-o', circuit])
        with open(circuit,'r') as f:
            return f.read()

    def compute_operating_point(self):
        spice = "Operating point simulation\n"
        spice += self.generate_spice()
        spice += ".op\n"
        spice += ".end\n"
        result = run_spice(spice)

        self._load_result(result, unary=True)

    def compute_dc_sweep(self, *sweeps):
        """ Syntax is compute_dc_sweep((Component, start, stop, step),...) """

        formatted = ' '.join(F"{component.name} {start} {stop} {step}" for component, start, stop, step in sweeps)
        spice = "Operating point simulation\n"
        spice += self.generate_spice()
        spice += F".dc {formatted}\n"
        spice += ".end\n"
        result = run_spice(spice)

        self._load_result(result)
        
    def compute_transient(self, stop, step):
        spice = "Operating point simulation\n"
        spice += self.generate_spice()
        spice += F".tran {step} {stop}\n"
        spice += ".end\n"
        result = run_spice(spice)

        self._load_result(result)

    def transient_analysis(self):
        pass

    def _load_result(self, result, unary=False):
        vec = result.get_plots()[0].get_scalevector()
        if vec.name == 'time':
            self.time = vec.get_data()
        else:
            kind, node = re.search("([a-zA-Z]+)\(([-a-zA-Z0-9]+)\)", vec.name).group(1, 2)
            if kind == 'v':
                if node.isdigit():
                    #print(node, vec.get_data())
                    self.operating_points[int(node)] = vec.get_data()[0] if unary else vec.get_data()
                else:
                    print("Ignoring node", node, vec.get_data())
            else:
                print("Ignoring type", kind)

        for vec in result.get_plots()[0].get_datavectors():
            kind, node = re.search("([a-zA-Z]+)\(([-a-zA-Z0-9]+)\)", vec.name).group(1, 2)
            if kind == 'v':
                if node.isdigit():
                    #print(node, vec.get_data())
                    self.operating_points[int(node)] = vec.get_data()[0] if unary else vec.get_data()
                else:
                    print("Ignoring node", node)
            else:
                print("Ignoring type", kind)

class Resistor(Component):
    IDX = 0

    def __init__(self, circuit, name=None, resistance=100):
        self.circuit = circuit
        self.circuit.add(self)

        self.resistance = resistance
        self.ports = [Port(circuit, component=self), Port(circuit, component=self)]
        self.top = self.neg = self.ports[0]
        self.bottom = self.pos = self.ports[1]
        self.name = "R" + str(Resistor.IDX)
        Resistor.IDX += 1

    def generate_spice(self):
        return F"{self.name} {self.pos.node} {self.neg.node} {self.resistance}"

    def json(self):
        return {
                'type': 'r_v',
                'connections': {
                    'A': [self.top.node],
                    'B': [self.bottom.node]
                },
                'attributes': {
                    'value': str(self.resistance)
                }}
    
class Capacitor(Component):
    IDX = 0

    def __init__(self, circuit, name=None, capacitance=1e-9):
        self.circuit = circuit
        self.circuit.add(self)

        self.capacitance = capacitance
        self.ports = [Port(circuit, component=self), Port(circuit, component=self)]
        self.top = self.neg = self.ports[0]
        self.bottom = self.pos = self.ports[1]
        self.name = "C" + str(Capacitor.IDX)
        Capacitor.IDX += 1

    def generate_spice(self):
        return F"{self.name} {self.pos.node} {self.neg.node} {self.capacitance}"

    def json(self):
        return {
                'type': 'c_v',
                'connections': {
                    'A': [self.top.node],
                    'B': [self.bottom.node]
                },
                'attributes': {
                    'value': str(self.capacitance)
                }}

class Voltage(Component):
    IDX = 0

    def __init__(self, circuit, name=None, voltage=1, ac=False, piecewise=None):
        """piecewise = [time voltage time voltage....]"""
        self.circuit = circuit
        self.circuit.add(self)

        self.voltage = voltage
        self.ac = ac
        self.piecewise = piecewise
        self.pos = Port(circuit, component=self)
        self.neg = Port(circuit, component=self)
        self.name = "V" + str(Voltage.IDX)
        Voltage.IDX += 1

    def generate_spice(self):
        if self.piecewise:
            timing = ' '.join([F"{self.piecewise[2*i]}s {self.piecewise[2*i+1]}" for i in range(len(self.piecewise)//2)])
            return F"{self.name} {self.pos.node} {self.neg.node} pwl {timing}"
        else:
            isAC = ' ac' if self.ac else ''
            return F"{self.name} {self.pos.node} {self.neg.node}{isAC} {self.voltage}"

    def json(self):
        return {
                'type': 'v',
                'connections': {
                    '+': [self.pos.node],
                    '-': [self.neg.node]
                },
                'attributes': {
                    'value': str(self.voltage)
                }}