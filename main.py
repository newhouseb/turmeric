from subprocess import Popen, PIPE

def run_spice(spice):
    return Popen(['ngspice', '-a', '-b'], stdin=PIPE, stdout=PIPE).communicate(input=spice.encode())[0]

class Circuit(object):
    def __init__(self):
        self.node_count = 1 # 0 is allocated to GND
        self.components = []

    def add(self, component):
        self.components.append(component)
        return component

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
        print(result)

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

    def __init__(self, name=None, resistance=100):
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

    def __init__(self, name=None, voltage=1):
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
dc = c.add(DCVoltage(voltage=2))
r1 = c.add(Resistor(resistance=100))
r2 = c.add(Resistor(resistance=100))
c.ground(dc.neg, r2.bottom)
c.connect(dc.pos, r1.top)
c.connect(r1.bottom, r2.top)
print(c.operating_point())

