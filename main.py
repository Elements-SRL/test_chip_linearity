# This is a sample Python script.
import csv
import sys
import time
import er4CommLib_python as er4


eps = 62.5 / 1e6


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
    er4.setVoltageRange(0)
    er4.setVoltageReferenceRange(0)
    er4.setSamplingRate(0)


def warmup():
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
        dv = (vpos.value - vneg.value)/1000
        di = (ipos - ineg) / 1e9
        rl = -dv/di if di != 0 else 0
        if abs(rl - rl_prec) > 50_000:
            c += 1
            go_on = c < 3
        else:
            rl_prec = rl
            c = 0
        # time.sleep(300)
    return rl


def acquire(ch_idx):
    er4.purgeData()
    data = []
    while len(data) < 1250:
        err, qs = er4.getQueueStatus()
        if err != er4.ErrorCode.Success:
            time.sleep(0.01)
            continue
        err, packets_read, buffer = er4.readData(qs.availableDataPackets)
        tuples = [er4.convertCurrentValue(int(d[ch_idx+1]), ch_idx) for d in buffer]
        data_in_channel = [t[1] for t in tuples if t[0] == er4.ErrorCode.Success]
        data = data + data_in_channel
    return sum(data)/len(data)


def get_next_v_dac_ext(v, di, r):
    return v + di*r if abs(di*r) > eps else v + eps * 1 if di > 0 else -1


def converge(v, r, ch_idx):
    v_dac_ext_measurement = er4.Measurement(v, er4.UnitPfxMilli, "V")
    er4.applyDacExt(v_dac_ext_measurement)
    I = acquire(ch_idx)/1e9
    # print("I "+str(I))
    # print("I0 "+str(I0))
    di = abs(I - I0)
    print(str(di))
    next_value = get_next_v_dac_ext(v_dac_ext_measurement.value, di, r)
    return v if di < Ith else converge(next_value, r, ch_idx)


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    csv_rows = [["V Dac internal", "V Dac External"]]
    # Current
    I0 = -10/1e9
    # Current threshold
    Ith = 0.0122/1e9
    if not connect():
        sys.exit(0)
    configure()
    rl = warmup()
    print("rl is " + str(rl))
    for v_dac_in_value in range(-500, 501):
        print("V Dac in is " + str(v_dac_in_value))
        v_dac_in_measurement = er4.Measurement(v_dac_in_value, er4.UnitPfxMilli, "V")
        # (from 0 to 15)
        for chIdx in range(16):
            er4.setVoltageOffset(chIdx, v_dac_in_measurement)
            v_dac_ext_value = v_dac_in_value + rl * I0
            vf = converge(v_dac_ext_value, rl, chIdx)
            csv_rows.append([v_dac_in_value, vf])
    er4.disconnect()
    er4.deinit()
    with open('LinearityLog.csv', 'w', newline='') as csvfile:
        linearity_csv = csv.writer(csvfile, delimiter=',')
        linearity_csv.writerows(csv_rows)
