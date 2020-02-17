from subprocess import Popen, PIPE
from ngspice_read import ngspice_read
import tempfile
import os

def run_spice(spice):
    raw_file = os.path.join(tempfile.mkdtemp(), "spice.raw")
    Popen(['ngspice', '-a', '-b', '-r' + raw_file], stdin=PIPE, stdout=PIPE).communicate(input=spice.encode())
    return ngspice_read(raw_file)

class Circuit(object):
    def __init__(self):
        self.node_count = 1 # 0 is allocated to GND
        self.components = []

    def add(self, component):
        self.components.append(component)

    def connect(self, *args):
        node = self.node_count
        for arg in args:
            arg.node = node
        self.node_count += 1

    def ground(self, *args):
        for arg in args:
            arg.node = 0

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

class Component(object):
    def __init__(self, prefix=None, name=None):
        pass

class Port(object):
    def __init__(self):
        self.node = None

class Resistor(object):
    IDX = 0

    def __init__(self, circuit, name=None, resistance=100):
        self.circuit = circuit
        self.circuit.add(self)

        self.resistance = resistance
        self.ports = [Port(), Port()]
        self.top = self.neg = self.ports[0]
        self.bottom = self.pos = self.ports[1]
        self.name = "R" + str(Resistor.IDX)
        Resistor.IDX += 1

    def generate_spice(self):
        return F"{self.name} {self.pos.node} {self.neg.node} {self.resistance}"

class DCVoltage(object):
    IDX = 0

    def __init__(self, circuit, name=None, voltage=1):
        self.circuit = circuit
        self.circuit.add(self)

        self.voltage = voltage
        self.pos = Port()
        self.neg = Port()
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
#
# dc.neg = c.ground
# dc.pos = r1.top
# r1.bottom = r2.top
# r2.bottom = c.ground

c = Circuit()
dc = DCVoltage(c, voltage=2)
r1 = Resistor(c, resistance=100)
r2 = Resistor(c, resistance=50)
c.ground(dc.neg, r2.bottom)
c.connect(dc.pos, r1.top)
c.connect(r1.bottom, r2.top)
print(c.operating_point())

