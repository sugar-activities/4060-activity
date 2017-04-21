import commands
import logging
import os

import common.Config as Config

def system(*args):
    cmd = ' '.join(args)
    logging.debug('[system] %s' % cmd)

    status = commands.getstatusoutput(cmd)
    logging.debug('[system][out] %d: %s' % status)

    return status

def arecord(duration, crop_csd, dst):
    tmp_file = os.path.join(Config.TMP_DIR, 'tempMic.wav')
    out_file = os.path.join(Config.TMP_DIR, 'micTemp.wav')
    crop_file = os.path.join(Config.FILES_DIR, crop_csd)
    dst_file = os.path.join(Config.DATA_DIR, dst)

    if system(Config.ARECORD, "-d", str(duration), tmp_file)[0] != 0:
        logging.error('arecord failed')
        return False

    system("csound", "--strset999=" + Config.TMP_DIR, crop_file)

    if os.path.isfile(dst):
        os.remove(dst_file)

    if os.path.isfile(out_file):
        os.rename(out_file, dst_file)
        os.remove(tmp_file)
    else:
        logging.debug('crop failed')
        os.rename(tmp_file, dst_file)
