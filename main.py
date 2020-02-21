from subprocess import Popen, PIPE
from ngspice_read import ngspice_read
import tempfile
import os
import re

from pygraphviz import *

def run_spice(spice):
    print(spice)
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
        circuit.edges.append((first, second))
    else:
        pass
    circuit.node_count += 1
    return Port(circuit, node=node)

GROUND = 'gnd'

def ground(*args):
    # Deduce the circuit
    circuit = None
    for arg in args:
        if isinstance(arg, Port):
            if circuit is None:
                circuit = arg.circuit
        else:
            for port in arg.ports:
                if circuit is None:
                    circuit = port.circuit

    for arg in args:
        if isinstance(arg, Port):
            arg.node = 0
            circuit.edges.append((arg.component, GROUND))
        else:
            for port in arg.ports:
                if port.node is None:
                    port.node = 0
                    circuit.edges.append((arg, GROUND))
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

        self.dummy_nodes = []
        self.edges = []

    def add(self, component):
        self.components.append(component)

    def generate_spice(self):
        spice = ""
        for component in self.components:
            spice += component.generate_spice() + "\n"
        return spice

    def render(self):
        g = AGraph()
        g.graph_attr['splines'] = 'ortho'
        g.graph_attr['nodesep'] = '1'
        for component in self.components:
            g.add_node(component.name)
        for edge in self.edges:
            g.add_edge(edge[0].name, edge[1].name if hasattr(edge[1], 'name') else edge[1])
        g.layout(prog='dot')
        g.draw('circuit.png')

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

    def transient_analysis(self):
        pass

    def _load_result(self, result, unary=False):
        vec = result.get_plots()[0].get_scalevector()
        print(vec.name)
        kind, node = re.search("([a-zA-Z]+)\(([-a-zA-Z0-9]+)\)", vec.name).group(1, 2)
        if kind == 'v':
            if node.isdigit():
                print(node, vec.get_data())
                self.operating_points[int(node)] = vec.get_data()[0] if unary else vec.get_data()
            else:
                print("Ignoring node", node, vec.get_data())
        else:
            print("Ignoring type", kind)

        for vec in result.get_plots()[0].get_datavectors():
            kind, node = re.search("([a-zA-Z]+)\(([-a-zA-Z0-9]+)\)", vec.name).group(1, 2)
            if kind == 'v':
                if node.isdigit():
                    print(node, vec.get_data())
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

class DCVoltage(Component):
    IDX = 0

    def __init__(self, circuit, name=None, voltage=1):
        self.circuit = circuit
        self.circuit.add(self)

        self.voltage = voltage
        self.pos = Port(circuit, component=self)
        self.neg = Port(circuit, component=self)
        self.name = "V" + str(DCVoltage.IDX)
        DCVoltage.IDX += 1

    def generate_spice(self):
        return F"{self.name} {self.pos.node} {self.neg.node} {self.voltage}"

c = Circuit()
dc = DCVoltage(c, voltage=2)
#dc2 = DCVoltage(c, voltage=1)

r1 = Resistor(c, resistance=100)
r2 = Resistor(c, resistance=50)
#r3 = Resistor(c, resistance=50)
ground(dc.neg, r2) #, r3, dc2.neg)
connect(dc.pos, r1)
div = connect(r1, r2) #, r3, dc2.pos)


c.compute_operating_point()
print(div.voltage)

c.compute_dc_sweep((dc, 0, 1, 0.5)) #, (dc2, 0, 1, 0.5))
print(div.voltage)

c.render()
