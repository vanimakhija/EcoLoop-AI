from eppy.modeleditor import IDF

IDD = r"C:\EnergyPlusV26-1-0\Energy+.idd"
IDF.setiddname(IDD)

idf = IDF("energyplus/baseline.idf")

print("=" * 60)
print("SCHEDULE:COMPACT")
print("=" * 60)

for s in idf.idfobjects["SCHEDULE:COMPACT"]:
    print(s.Name)

print("\n" + "=" * 60)
print("THERMOSTATSETPOINT:DUALSETPOINT")
print("=" * 60)

for t in idf.idfobjects["THERMOSTATSETPOINT:DUALSETPOINT"]:
    print(t.Name)