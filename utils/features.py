import os
import sys
sys.path.insert(1, os.path.join(sys.path[0], 'utils'))
import numpy as np
import pandas as pd
import argparse
import h5py
import librosa
from scipy import signal
import matplotlib.pyplot as plt
import time
import csv
import random

from utilities import read_audio, create_folder
import config


class LogMelExtractor():
    def __init__(self, sample_rate, window_size, overlap, mel_bins):
        
        self.window_size = window_size
        self.overlap = overlap
        self.ham_win = np.hamming(window_size)
        
        self.melW = librosa.filters.mel(sr=sample_rate, 
                                        n_fft=window_size, 
                                        n_mels=mel_bins, 
                                        fmin=20., 
                                        fmax=sample_rate // 2).T
    
    def transform(self, audio):
    
        ham_win = self.ham_win
        window_size = self.window_size
        overlap = self.overlap
    
        [f, t, x] = signal.spectral.spectrogram(
                        audio, 
                        window=ham_win,
                        nperseg=window_size, 
                        noverlap=overlap, 
                        detrend=False, 
                        return_onesided=True, 
                        mode='magnitude') 
        x = x.T
            
        x = np.dot(x, self.melW)
        x = np.log(x + 1e-8)
        x = x.astype(np.float32)
        
        return x


def calculate_logmel(audio_path, sample_rate, feature_extractor):
    
    # Read audio
    (audio, fs) = read_audio(audio_path, target_fs=sample_rate)
    
    '''We do not divide the maximum value of an audio here because we assume 
    the low energy of an audio may also contain information of a scene. '''
    
    # Extract feature
    feature = feature_extractor.transform(audio)
    
    return feature


def read_development_meta(meta_csv):
    
    df = pd.read_csv(meta_csv)
    df = pd.DataFrame(df)
    
    audio_names = []
    emotion_labels = []

    for row in df.iterrows():
        
        audio_name = row[1]['filename']
        emotion_label = row[1]['emo']

        audio_names.append(audio_name)
        emotion_labels.append(emotion_label)
        
    return audio_names, emotion_labels
    

def calculate_features(args):
    
    # Arguments & parameters
    dataset_dir = args.dataset_dir
    # subdir = args.subdir
    data_type = args.data_type
    workspace = args.workspace
    mini_data = args.mini_data

    sample_rate = config.sample_rate
    window_size = config.window_size
    overlap = config.overlap
    seq_len = config.seq_len
    mel_bins = config.mel_bins
    
    # Paths
    audio_dir = dataset_dir
    
    if data_type == 'development':
        # meta_csv = os.path.join(dataset_dir, 'zhao_code', 'demos_data', 'meta.csv')
        meta_csv = "/home/nwang/emotion/dataset/DEMOS/meta.csv"

    hdf5_path = os.path.join(workspace, 'features', 'logmel', '{}.h5'.format(data_type))

    create_folder(os.path.dirname(hdf5_path))
    
    # Feature extractor
    feature_extractor = LogMelExtractor(sample_rate=sample_rate, 
                                        window_size=window_size, 
                                        overlap=overlap, 
                                        mel_bins=mel_bins)

    # Read meta csv
    if data_type == 'development':
        [audio_names, emotion_labels] = read_development_meta(meta_csv)
        
    print('Number of audios: {}'.format(len(audio_names)))
    
    # Create hdf5 file
    hf = h5py.File(hdf5_path, 'w')
    
    hf.create_dataset(
        name='feature', 
        shape=(0, seq_len, mel_bins), 
        maxshape=(None, seq_len, mel_bins), 
        dtype=np.float32)
    
    calculate_time = time.time()

    for (n, audio_name) in enumerate(audio_names):
        
        # print(n, audio_name)
        
        # Calculate feature
        audio_path = os.path.join(audio_dir, audio_name)
        
        # Extract feature
        feature = calculate_logmel(audio_path=audio_path, 
                                    sample_rate=sample_rate, 
                                    feature_extractor=feature_extractor)
        '''(seq_len, mel_bins)'''
        
        # print(feature.shape)

        # repeat
        if len(feature) < seq_len:
            stack_n1 = seq_len // len(feature) - 1
            stack_n2 = seq_len % len(feature)
            feature_temp = feature
            for n1 in range(0, stack_n1):
                feature = np.vstack((feature, feature_temp))
            feature = np.vstack((feature, feature_temp[0:stack_n2]))

        hf['feature'].resize((n + 1, seq_len, mel_bins))
        hf['feature'][n] = feature

        # Plot log Mel for debug
        if False:
            plt.matshow(feature.T, origin='lower', aspect='auto', cmap='jet')
            plt.show()
        
    # Write meta info to hdf5
    hf.create_dataset(name='filename', 
                      data=[s.encode() for s in audio_names], 
                      dtype='S50')
    

    hf.create_dataset(name='emotion_label',
                      data=[s.encode() for s in emotion_labels],
                      dtype='S20')

    hf.close()
    
    print('Write out hdf5 file to {}'.format(hdf5_path))
    print('Time spent: {} s'.format(time.time() - calculate_time))



if __name__ == '__main__':

    # this part is for debugging
    DATASET_DIR = "/home/nwang/emotion/dataset/DEMOS"
    WORKSPACE = "/home/nwang/Adversarial_Attacks_for_SER"
    DEV_SUBTASK_A_DIR = "development-subtaskA"
    parser = argparse.ArgumentParser(description='Example of parser. ')

    parser.add_argument('--mode', type=str, default='logmel')
    parser.add_argument('--dataset_dir', type=str, default=DATASET_DIR)
    # parser.add_argument('--subdir', type=str, default=DEV_SUBTASK_A_DIR)
    parser.add_argument('--workspace', type=str, default=WORKSPACE)
    parser.add_argument('--data_type', type=str, default='development')
    parser.add_argument('--mini_data', action='store_true', default=False)

    args = parser.parse_args()

    if args.mode == 'logmel':
        calculate_features(args)
    else:
        raise Exception('Incorrect arguments!')

    '''
    parser = argparse.ArgumentParser(description='')
    subparsers = parser.add_subparsers(dest='mode')

    parser_logmel = subparsers.add_parser('logmel')
    parser_logmel.add_argument('--dataset_dir', type=str, required=True)
    parser_logmel.add_argument('--subdir', type=str, required=True)
    parser_logmel.add_argument('--data_type', type=str, required=True, choices=['development', 'leaderboard', 'evaluation'])
    parser_logmel.add_argument('--workspace', type=str, required=True)
    parser_logmel.add_argument('--mini_data', action='store_true', default=False)
    
    args = parser.parse_args()
    
    if args.mode == 'logmel':
        
        calculate_features(args)
        
    else:
        raise Exception('Incorrect arguments!')
    '''
