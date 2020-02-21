from subprocess import Popen, PIPE
from ngspice_read import ngspice_read
import tempfile
import os

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
    circuit.node_count += 1

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
    def __init__(self, circuit):
        self.circuit = circuit
        self.node = None

class Component(object):
    def __init__(self, prefix=None, name=None):
        pass

class Circuit(object):
    def __init__(self):
        self.node_count = 1 # 0 is allocated to GND
        self.components = []

    def add(self, component):
        self.components.append(component)

    def generate_spice(self):
        spice = ""
        for component in self.components:
            spice += component.generate_spice() + "\n"
        return spice

    def operating_point(self):
        spice = "Operating point simulation\n"
        spice += self.generate_spice()
        spice += ".op\n"
        spice += ".end\n"
        result = run_spice(spice)

        vec = result.get_plots()[0].get_scalevector()
        print(vec.name, vec.get_data())
        for vec in result.get_plots()[0].get_datavectors():
            print(vec.name, vec.get_data())

    def transient_analysis(self):
        pass


class Resistor(Component):
    IDX = 0

    def __init__(self, circuit, name=None, resistance=100):
        self.circuit = circuit
        self.circuit.add(self)

        self.resistance = resistance
        self.ports = [Port(circuit), Port(circuit)]
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
        self.pos = Port(circuit)
        self.neg = Port(circuit)
        self.name = "V" + str(DCVoltage.IDX)
        DCVoltage.IDX += 1

    def generate_spice(self):
        return F"{self.name} {self.pos.node} {self.neg.node} {self.voltage}"

# dc = DCVoltage(1)
# r1 = Resistor(100)
# r2 = Resistor(100)
# connect(dc.pos, r1)
# connect(r1, r2)
# ground(r2)
# ground(dc.neg)

c = Circuit()
dc = DCVoltage(c, voltage=2)
r1 = Resistor(c, resistance=100)
r2 = Resistor(c, resistance=50)
r3 = Resistor(c, resistance=50)
ground(dc.neg, r2, r3)
connect(dc.pos, r1)
connect(r1, r2, r3)
print(c.operating_point())

