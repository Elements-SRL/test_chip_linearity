# This is a sample Python script.
import csv
import sys
import time
import er4CommLib_python as er4


eps = 62.5e-6


def connect():
    er4.init()
    err, devices = er4.detectDevices()
    if len(devices) > 0:
        er4.connect(devices[0])
        return True
    else:
        res = er4.connect("e16 Demo")
        print(res == er4.ErrorCode.Success)
        print("no device connected")
        return False


def configure():
    er4.setCurrentRange(0, 16)
    er4.setVoltageRange(0)
    er4.setVoltageReferenceRange(0)
    er4.setSamplingRate(0)


def warmup():
    # printo valori di resistenza iterativamente
    go_on = True
    rl_prec = 10_000_000
    rl = 10_000_111
    c = 0
    while go_on:
        vpos = er4.Measurement(100, er4.UnitPfxMilli, "V")
        vneg = er4.Measurement(-100, er4.UnitPfxMilli, "V")
        er4.applyDacExt(vpos)
        ipos = acquire(0)
        er4.applyDacExt(vneg)
        ineg = acquire(0)
        print(str(ipos), str(ineg))
        dv = (vpos.value - vneg.value)/1000
        di = (ipos - ineg) / 1e9
        rl = dv/di if di != 0 else 0
        print(str(di), str(abs(rl - rl_prec)), rl)
        if abs(rl - rl_prec) > 50_000:
            c += 1
            go_on = c < 5
        else:
            rl_prec = rl
            c = 0
        time.sleep(3)
    return rl


# Value of current in nA
def acquire(ch_idx):
    er4.purgeData()
    data = []
    while len(data) < 1250:
        err, qs = er4.getQueueStatus()
        if err != er4.ErrorCode.Success:
            # wait for data
            time.sleep(0.01)
            continue
        err, packets_read, buffer = er4.readData(qs.availableDataPackets)
        tuples = [er4.convertCurrentValue(int(d[ch_idx+1]), ch_idx) for d in buffer]
        data_in_channel = [t[1] for t in tuples if t[0] == er4.ErrorCode.Success]
        data = data + data_in_channel
    return sum(data)/len(data)


def get_next_v_dac_ext(v, di, r):
    s = 1 if di > 0 else -1
    if abs(di*r) > eps:
        print("v + di * r")
    else:
        print("v + eps * s")
    return (v + di * r) if abs(di * r) > eps else (v + eps * s)


def converge(v, r, ch_idx, c=0):
    v_dac_ext_measurement = er4.Measurement(v, er4.UnitPfxNone, "V")
    er4.applyDacExt(v_dac_ext_measurement)
    # convert to A
    I = acquire(ch_idx)/1e9
    di = I - I0
    next_value = get_next_v_dac_ext(v_dac_ext_measurement.value, di, r)
    print("difference with sign " + str(I-I0), "difference (abs) " + str(di - Ith), "next dac value " + str(next_value))
    return v if (di < Ith or c > 500) else converge(next_value, r, ch_idx, c + 1)


if __name__ == '__main__':
    csv_rows = [["V Dac internal", "V Dac External"]]
    # Current
    I0 = -10e-9
    # Current threshold
    Ith = 0.0122e-9
    if not connect():
        sys.exit(0)
    configure()
    rl = warmup()
    print("rl is " + str(rl))
    time.sleep(5)
    for v_dac_in_mV in range(-500, 501):
        print("V Dac in is " + str(v_dac_in_mV))
        v_dac_in_value = v_dac_in_mV / 1000
        v_dac_in_measurement = er4.Measurement(v_dac_in_value, er4.UnitPfxNone, "V")
        # (from 0 to 15)
        for chIdx in range(1):
            er4.setVoltageOffset(chIdx, v_dac_in_measurement)
            v_dac_ext_value = v_dac_in_value + rl * I0
            vf = converge(v_dac_ext_value, rl, chIdx)
            csv_rows.append([v_dac_in_value, vf])
    er4.disconnect()
    er4.deinit()
    with open('LinearityLog.csv', 'w', newline='') as csvfile:
        linearity_csv = csv.writer(csvfile, delimiter=',')
        linearity_csv.writerows(csv_rows)
