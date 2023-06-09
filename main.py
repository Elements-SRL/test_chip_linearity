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
        print("no device connected")
        return False


def configure():
    er4.setCurrentRange(0, 16)
    er4.setVoltageRange(0)
    er4.setVoltageReferenceRange(0)
    er4.setSamplingRate(0)


def find_resistence(ch_idx, rl_prev=10_000_000, c=0):
    if c > 5:
        return rl_prev
    # time.sleep(3)
    vpos = er4.Measurement(100, er4.UnitPfxMilli, "V")
    vneg = er4.Measurement(-100, er4.UnitPfxMilli, "V")
    er4.applyDacExt(vpos)
    ipos = acquire(ch_idx)
    er4.applyDacExt(vneg)
    ineg = acquire(ch_idx)
    dv = (vpos.value - vneg.value) / 1000
    di = (ipos - ineg) / 1e9
    rl = dv / di if di != 0 else 0
    return find_resistence(ch_idx, rl_prev, c+1) if abs(rl - rl_prev) < 500_000 else find_resistence(ch_idx, rl, 0)


# Value of current in nA
def acquire(ch_idx):
    time.sleep(0.2)
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
    return (v - di * r) if abs(di * r) > eps else (v - eps * s)


def converge(v, r, ch_idx, c=0):
    v_dac_ext_measurement = er4.Measurement(v, er4.UnitPfxNone, "V")
    er4.applyDacExt(v_dac_ext_measurement)
    # convert to A
    I = acquire(ch_idx)/1e9
    di = I - I0
    next_value = get_next_v_dac_ext(v_dac_ext_measurement.value, di, r)
    return v if (abs(di) < Ith or c > 500) else converge(next_value, r, ch_idx, c + 1)


def find_vf_dac_ext(ch_idx, r, initial_v_dac_in_measurement, initial_v_dac_in_value):
    er4.setVoltageOffset(ch_idx, initial_v_dac_in_measurement)
    v_dac_ext_value = initial_v_dac_in_value + r * I0
    return converge(v_dac_ext_value, r, ch_idx)


if __name__ == '__main__':
    csv_resistors_rows = [["R0", "R1", "R2", "R3", "R4", "R8", "R10", "R11", "R12", "R13", "R14"]]
    csv_rows = [["VD_i ", "VD_e0", "VD_e1", "VD_e2", "VD_e3", "VD_e4",
                 "VD_e8", "VD_e10", "VD_e11", "VD_e12", "VD_e13", "VD_e14"]]
    # Current
    I0 = 10e-9
    # Current threshold
    Ith = 0.0122e-9
    if not connect():
        sys.exit(0)
    configure()
    # channel_indexes = [i for i in range(16)]
    channel_indexes = [0, 1, 2, 3, 4, 8, 10, 11, 12, 13, 14]
    rls = [find_resistence(c) for c in channel_indexes]
    print(str(rls))
    csv_resistors_rows.append(rls)
    with open('ResistorsLog.csv', 'w', newline='') as csvfile:
        resistors_csv = csv.writer(csvfile, delimiter=',')
        resistors_csv.writerows(csv_resistors_rows)
    for v_dac_in_mV in range(-500, 501):
        print("V Dac in is " + str(v_dac_in_mV))
        v_dac_in_value = v_dac_in_mV / 1000
        v_dac_in_measurement = er4.Measurement(v_dac_in_value, er4.UnitPfxNone, "V")
        vfs = [find_vf_dac_ext(c, rls[channel_indexes.index(c)], v_dac_in_measurement, v_dac_in_value) for c in channel_indexes]
        csv_rows.append([v_dac_in_value]+vfs)
    er4.disconnect()
    er4.deinit()
    with open('LinearityLog.csv', 'w', newline='') as csvfile:
        linearity_csv = csv.writer(csvfile, delimiter=',')
        linearity_csv.writerows(csv_rows)
