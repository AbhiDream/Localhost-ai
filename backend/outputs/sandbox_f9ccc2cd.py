
import math

def calculate_LMTD(Th_in, Th_out, Tc_in, Tc_out):
    dT1 = Th_in - Tc_out
    dT2 = Th_out - Tc_in
    if dT1 == dT2:
        return dT1
    LMTD = (dT1 - dT2) / math.log(dT1 / dT2)
    return LMTD

result = calculate_LMTD(150, 90, 30, 70)
print(f"LMTD = {result:.2f} degrees")
print(f"Hot side: 150->90, Cold side: 30->70")
print("Calculation successful!")
