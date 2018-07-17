from __future__ import print_function
from model import LMF
from utils import MultimodalDataset, total
from torch.utils.data import DataLoader, Dataset
from torch.autograd import Variable
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
import os
import argparse
import torch
import random
import torch.nn as nn
import torch.optim as optim
import numpy as np
import csv
import cPickle as pickle
import time

def load_pom(max_segment_len = 20, verbose = False):
    '''
    load the pom dataset
    :param max_segment_len: 
    :param verbose: print debug info or not
    :return: 
    '''
    # get sums_dict to segment video into sentence and average across sentence
    sums_dict = dict()
    trans_dir = '/media/bighdd4/Prateek/datasets/aligned_dataset/POM/Raw/Transcript/Full/'
    arr = os.listdir(trans_dir)
    for file in arr:
        file_dir = '/media/bighdd4/Prateek/datasets/aligned_dataset/POM/Raw/Transcript/Full/%s' % file
        with open(file_dir) as trans:
            sens = trans.read().split('.')
            sums = []
            total = 0
            for sen in sens:
                sen = sen.strip()
                num_words = len(sen.split())
                sums.append(total)
                total += num_words
        video_id = file[:-4]
        if video_id not in sums_dict:
            sums_dict[video_id] = dict()
        sums_dict[video_id]['1'] = sums

    # get labels
    labels_csv = '/media/bighdd4/Prateek/datasets/aligned_dataset/POM/Labels/OurPOM/movie_review_main_HIT_all_icmi.csv'
    labels = dict()
    want = [35, 36, 40, 42, 43, 44, 46, 47, 48, 49, 51, 53, 55, 57, 61, 63, 65]
    # persuasion is 63
    # want = [63]
    with open(labels_csv) as csvfile:
        f = csv.reader(csvfile)
        i = 0
        for line in f:
            i += 1
            if i == 1:
                continue
            link = line[33]
            video_id = link[link.rfind('/') + 1:]
            video_id = video_id[:video_id.index('.')]
            segment = '1'
            l = np.array([float(line[i][:line[i].index('_')]) for i in want])
            if video_id not in labels:
                labels[video_id] = dict()
            if segment not in labels[video_id]:
                labels[video_id][segment] = np.array([0.0 for i in want])
            labels[video_id][segment] += l / 3.0

    error_i = []
    for video_id in sums_dict:
        if video_id not in labels:
            error_i.append(video_id)

    dict_dir = "/media/bighdd4/Paul/mosi2/experiments/pom/"
    text_dict = pickle.load(open(dict_dir+"text_dict_s.p", "rb"))
    audio_dict = pickle.load(open(dict_dir+"audio_dict_s.p", "rb"))
    video_dict = pickle.load(open(dict_dir+"video_dict_s.p", "rb"))

    def pad(data, max_segment_len, t):
        curr = []
        dim = data.shape[1]
        if t == 1 and dim != 300:
            return np.zeros((max_segment_len, 300))
        if t == 2 and dim != 43:
            return np.zeros((max_segment_len, 43))
        if t == 3 and dim != 41:
            return np.zeros((max_segment_len, 41))
        if max_segment_len >= len(data):
            for i in xrange(max_segment_len - len(data)):
                curr.append([0 for i in xrange(dim)])
            for vec in data:
                curr.append(vec)
        else:  # max_segment_len < len(text), take last max_segment_len of text
            for vec in data[len(data) - max_segment_len:]:
                curr.append(vec)
        curr = np.array(curr)
        return curr

    all_ids = []
    for video_id in text_dict:
        if video_id not in error_i:
            all_ids.append((video_id, '1'))
    train_i = all_ids[:600]
    valid_i = all_ids[600:700]
    test_i = all_ids[700:]

    text_train_emb = np.nan_to_num(
        np.array([pad(text_dict[video_id][segment_id], max_segment_len, 1) for (video_id, segment_id) in train_i]))
    covarep_train = np.nan_to_num(
        np.array([pad(audio_dict[video_id][segment_id], max_segment_len, 2) for (video_id, segment_id) in train_i]))
    facet_train = np.nan_to_num(
        np.array([pad(video_dict[video_id][segment_id], max_segment_len, 3) for (video_id, segment_id) in train_i]))
    y_train = np.nan_to_num(np.array([labels[video_id][segment_id] for (video_id, segment_id) in train_i]))

    text_valid_emb = np.nan_to_num(
        np.array([pad(text_dict[video_id][segment_id], max_segment_len, 1) for (video_id, segment_id) in valid_i]))
    covarep_valid = np.nan_to_num(
        np.array([pad(audio_dict[video_id][segment_id], max_segment_len, 2) for (video_id, segment_id) in valid_i]))
    facet_valid = np.nan_to_num(
        np.array([pad(video_dict[video_id][segment_id], max_segment_len, 3) for (video_id, segment_id) in valid_i]))
    y_valid = np.nan_to_num(np.array([labels[video_id][segment_id] for (video_id, segment_id) in valid_i]))

    text_test_emb = np.nan_to_num(
        np.array([pad(text_dict[video_id][segment_id], max_segment_len, 1) for (video_id, segment_id) in test_i]))
    covarep_test = np.nan_to_num(
        np.array([pad(audio_dict[video_id][segment_id], max_segment_len, 2) for (video_id, segment_id) in test_i]))
    facet_test = np.nan_to_num(
        np.array([pad(video_dict[video_id][segment_id], max_segment_len, 3) for (video_id, segment_id) in test_i]))
    y_test = np.nan_to_num(np.array([labels[video_id][segment_id] for (video_id, segment_id) in test_i]))

    facet_train_max = np.max(np.max(np.abs(facet_train), axis=0), axis=0)
    facet_train_max[facet_train_max == 0] = 1
    covarep_train_max = np.max(np.max(np.abs(covarep_train), axis=0), axis=0)
    covarep_train_max[covarep_train_max == 0] = 1

    facet_train = facet_train / facet_train_max
    facet_valid = facet_valid / facet_train_max
    facet_test = facet_test / facet_train_max
    covarep_train = covarep_train / covarep_train_max
    covarep_valid = covarep_valid / covarep_train_max
    covarep_test = covarep_test / covarep_train_max

    # average audio & video features
    facet_train = facet_train.mean(axis=1)
    facet_valid = facet_valid.mean(axis=1)
    facet_test = facet_test.mean(axis=1)

    covarep_train = covarep_train.mean(axis=1)
    covarep_valid = covarep_valid.mean(axis=1)
    covarep_test = covarep_test.mean(axis=1)

    if verbose:
        print(text_train_emb.shape)  # 600 x seq x 300
        print(covarep_train.shape)  # n x seq x 43
        print(facet_train.shape)  # n x seq x 41

        print(text_valid_emb.shape)  # 100 x seq x 300
        print(covarep_valid.shape) # n x seq x 43
        print(facet_valid.shape)  # n x seq x 41

        print(text_test_emb.shape)  # 203 x seq x 300
        print(covarep_test.shape)  # n x seq x 43
        print(facet_test.shape)  # n x seq x 41


    return covarep_train, facet_train, text_train_emb, y_train, \
           covarep_valid, facet_valid, text_valid_emb, y_valid, \
           covarep_test, facet_test, text_test_emb, y_test

def preprocess():
    # parse the input args
    class POM(Dataset):
        '''
        PyTorch Dataset for POM, don't need to change this
        '''
        def __init__(self, audio, visual, text, labels):
            self.audio = audio
            self.visual = visual
            self.text = text
            self.labels = labels
        
        def __getitem__(self, idx):
            return [self.audio[idx, :], self.visual[idx, :], self.text[idx, :, :], self.labels[idx]]

        def __len__(self):
            return self.audio.shape[0]


    # TODO: put the data loading code here, so you can populate xxx_audio, xxx_visual, xxx_text and xxx_labels with numpy
    # arrays. xxx_audio and xxx_visual should be of shape (num_examples, feature_dim), and xxx_text will be (num_examples, maxlen, feature_dim)
    # xxx_labels will be of shape (num_examples, output_dim)

    
    train_audio, train_visual, train_text, train_labels, \
    valid_audio, valid_visual, valid_text, valid_labels, \
    test_audio, test_visual, test_text, test_labels = load_pom()

    # code that instantiates the Dataset objects
    train_set = POM(train_audio, train_visual, train_text, train_labels)
    valid_set = POM(valid_audio, valid_visual, valid_text, valid_labels)
    test_set = POM(test_audio, test_visual, test_text, test_labels)


    audio_dim = train_set[0][0].shape[0]
    print("Audio feature dimension is: {}".format(audio_dim))
    visual_dim = train_set[0][1].shape[0]
    print("Visual feature dimension is: {}".format(visual_dim))
    text_dim = train_set[0][2].shape[1]
    print("Text feature dimension is: {}".format(text_dim))
    input_dims = (audio_dim, visual_dim, text_dim)

    # remove possible NaN values
    train_set.visual[train_set.visual != train_set.visual] = 0
    valid_set.visual[valid_set.visual != valid_set.visual] = 0
    test_set.visual[test_set.visual != test_set.visual] = 0

    train_set.audio[train_set.audio != train_set.audio] = 0
    valid_set.audio[valid_set.audio != valid_set.audio] = 0
    test_set.audio[test_set.audio != test_set.audio] = 0

    return train_set, valid_set, test_set, input_dims

def display(mae, corr, mult_acc):
    print("MAE on test set is {}".format(mae))
    print("Correlation w.r.t human evaluation on test set is {}".format(corr))
    print("Multiclass accuracy on test set is {}".format(mult_acc))

def main(options):
    DTYPE = torch.FloatTensor

    # parse the input args
    run_id = options['run_id']
    epochs = options['epochs']
    model_path = options['model_path']
    output_path = options['output_path']
    signiture = options['signiture']
    patience = options['patience']

    print("Training initializing... Setup ID is: {}".format(run_id))

    # prepare the paths for storing models and outputs
    model_path = os.path.join(
        model_path, "model_{}_{}.pt".format(signiture, run_id))
    output_path = os.path.join(
        output_path, "results_{}_{}.csv".format(signiture, run_id))
    print("Temp location for models: {}".format(model_path))
    print("Grid search results are in: {}".format(output_path))

    train_set, valid_set, test_set, input_dims = preprocess()

    params = dict()
    params['audio_hidden'] = [4, 8, 16]
    params['video_hidden'] = [4, 8, 16]
    params['text_hidden'] = [64, 128, 256]
    params['audio_dropout'] = [0, 0.1, 0.15, 0.2, 0.3, 0.5]
    params['video_dropout'] = [0, 0.1, 0.15, 0.2, 0.3, 0.5]
    params['text_dropout'] = [0, 0.1, 0.15, 0.2, 0.3, 0.5]
    params['factor_learning_rate'] = [0.0003, 0.0005, 0.001, 0.003]
    params['learning_rate'] = [0.0003, 0.0005, 0.001, 0.003]
    params['rank'] = [1, 4, 8, 16]
    params['batch_size'] = [4, 8, 16, 32, 64, 128]
    params['weight_decay'] = [0, 0.001, 0.002, 0.01]

    total_settings = total(params)

    print("There are {} different hyper-parameter settings in total.".format(total_settings))

    seen_settings = set()

    with open(output_path, 'w+') as out:
        writer = csv.writer(out)
        writer.writerow(["audio_hidden", "video_hidden", 'text_hidden', 'audio_dropout', 'video_dropout', 'text_dropout',
                        'factor_learning_rate', 'learning_rate', 'rank', 'batch_size', 'weight_decay', 'Best Validation MAE', 

                        'Confidence accuracy',
                        'Passionate accuracy',
                        'Pleasant accuracy',
                        'Dominant accuracy',
                        'Credible accuracy',
                        'Vivid accuracy',
                        'Expertise accuracy',
                        'Entertaining accuracy',
                        'Reserved accuracy',
                        'Trusting accuracy',
                        'Relaxed accuracy',
                        'Outgoing accuracy',
                        'Thorough accuracy',
                        'Nervous accuracy',
                        'Sentiment accuracy',
                        'Persuasive accuracy',
                        'Humorous accuracy',

                        'Confidence MAE',
                        'Passionate MAE',
                        'Pleasant MAE',
                        'Dominant MAE',
                        'Credible MAE',
                        'Vivid MAE',
                        'Expertise MAE',
                        'Entertaining MAE',
                        'Reserved MAE',
                        'Trusting MAE',
                        'Relaxed MAE',
                        'Outgoing MAE',
                        'Thorough MAE',
                        'Nervous MAE',
                        'Sentiment MAE',
                        'Persuasive MAE',
                        'Humorous MAE',

                        'Confidence corr',
                        'Passionate corr',
                        'Pleasant corr',
                        'Dominant corr',
                        'Credible corr',
                        'Vivid corr',
                        'Expertise corr',
                        'Entertaining corr',
                        'Reserved corr',
                        'Trusting corr',
                        'Relaxed corr',
                        'Outgoing corr',
                        'Thorough corr',
                        'Nervous corr',
                        'Sentiment corr',
                        'Persuasive corr',
                        'Humorous corr'])

    for i in range(total_settings):

        ahid = random.choice(params['audio_hidden'])
        vhid = random.choice(params['video_hidden'])
        thid = random.choice(params['text_hidden'])
        thid_2 = thid / 2
        adr = random.choice(params['audio_dropout'])
        vdr = random.choice(params['video_dropout'])
        tdr = random.choice(params['text_dropout'])
        factor_lr = random.choice(params['factor_learning_rate'])
        lr = random.choice(params['learning_rate'])
        r = random.choice(params['rank'])
        batch_sz = random.choice(params['batch_size'])
        decay = random.choice(params['weight_decay'])

        # reject the setting if it has been tried
        current_setting = (ahid, vhid, thid, adr, vdr, tdr, factor_lr, lr, r, batch_sz, decay)
        if current_setting in seen_settings:
            continue
        else:
            seen_settings.add(current_setting)

        model = LMF(input_dims, (ahid, vhid, thid), thid_2, (adr, vdr, tdr, 0.5), 17, r)
        if options['cuda']:
            model = model.cuda()
            DTYPE = torch.cuda.FloatTensor
        print("Model initialized")
        criterion = nn.L1Loss(size_average=False)
        factors = list(model.parameters())[:3]
        other = list(model.parameters())[5:]
        optimizer = optim.Adam([{"params": factors, "lr": factor_lr}, {"params": other, "lr": lr}], weight_decay=decay) # don't optimize the first 2 params, they should be fixed (output_range and shift)

        # setup training
        complete = True
        min_valid_loss = float('Inf')
        train_iterator = DataLoader(train_set, batch_size=batch_sz, num_workers=4, shuffle=True)
        valid_iterator = DataLoader(valid_set, batch_size=len(valid_set), num_workers=4, shuffle=True)
        test_iterator = DataLoader(test_set, batch_size=len(test_set), num_workers=4, shuffle=True)
        curr_patience = patience
        for e in range(epochs):
            model.train()
            model.zero_grad()
            avg_train_loss = 0.0
            for batch in train_iterator:
                model.zero_grad()

                # the provided data has format [batch_size, seq_len, feature_dim] or [batch_size, 1, feature_dim]
                x = batch[:-1]
                x_a = Variable(x[0].float().type(DTYPE), requires_grad=False)
                x_v = Variable(x[1].float().type(DTYPE), requires_grad=False)
                x_t = Variable(x[2].float().type(DTYPE), requires_grad=False)
                y = Variable(batch[-1].view(-1, 17).float().type(DTYPE), requires_grad=False)
                output = model(x_a, x_v, x_t)
                loss = criterion(output, y)
                loss.backward()
                avg_loss = loss.data[0] / 17.0
                avg_train_loss += avg_loss / len(train_set)
                optimizer.step()

            print("Epoch {} complete! Average Training loss: {}".format(e, avg_train_loss))

            # Terminate the training process if run into NaN
            if np.isnan(avg_train_loss):
                print("Training got into NaN values...\n\n")
                complete = False
                break

            # On validation set we don't have to compute metrics other than MAE and accuracy
            model.eval()
            for batch in valid_iterator:
                x = batch[:-1]
                x_a = Variable(x[0].float().type(DTYPE), requires_grad=False)
                x_v = Variable(x[1].float().type(DTYPE), requires_grad=False)
                x_t = Variable(x[2].float().type(DTYPE), requires_grad=False)
                y = Variable(batch[-1].view(-1, 17).float().type(DTYPE), requires_grad=False)
                output = model(x_a, x_v, x_t)
                valid_loss = criterion(output, y)
                avg_valid_loss = valid_loss.data[0] / 17.0
            output_valid = output.cpu().data.numpy().reshape(-1, 17)
            y = y.cpu().data.numpy().reshape(-1, 17)

            if np.isnan(avg_valid_loss):
                print("Training got into NaN values...\n\n")
                complete = False
                break

            # valid_binacc = accuracy_score(output_valid>=0, y>=0)

            print("Validation loss is: {}".format(avg_valid_loss / len(valid_set)))
            # print("Validation binary accuracy is: {}".format(valid_binacc))

            if (avg_valid_loss < min_valid_loss):
                curr_patience = patience
                min_valid_loss = avg_valid_loss
                torch.save(model, model_path)
                print("Found new best model, saving to disk...")
            else:
                curr_patience -= 1
            
            if curr_patience <= 0:
                break
            print("\n\n")

        if complete:
            
            best_model = torch.load(model_path)
            best_model.eval()
            for batch in test_iterator:
                x = batch[:-1]
                x_a = Variable(x[0].float().type(DTYPE), requires_grad=False)
                x_v = Variable(x[1].float().type(DTYPE), requires_grad=False)
                x_t = Variable(x[2].float().type(DTYPE), requires_grad=False)
                y = Variable(batch[-1].view(-1, 17).float().type(DTYPE), requires_grad=False)
                output_test = model(x_a, x_v, x_t)
                loss_test = criterion(output_test, y)
                test_loss = loss_test.data[0]
                avg_test_loss = test_loss / 17.0
            output_test = output_test.cpu().data.numpy().reshape(-1, 17)
            y = y.cpu().data.numpy().reshape(-1, 17)

            # these are the needed metrics
            mae = np.mean(np.absolute(output_test - y), axis=0)
            mae = [round(a, 3) for a in mae]
            corr = [round(np.corrcoef(output_test[:, i], y[:, i])[0][1], 3) for i in xrange(y.shape[1])]
            mult_acc = [round(sum(np.round(output_test[:, i]) == np.round(y[:, i])) / float(len(y)), 3) for i in xrange(y.shape[1])]

            display(mae, corr, mult_acc)

            results = [ahid, vhid, thid, adr, vdr, tdr, factor_lr, lr, r, batch_sz, decay, min_valid_loss / len(valid_set)]

            results.extend(mult_acc)
            results.extend(mae)
            results.extend(corr)

            with open(output_path, 'a+') as out:
                writer = csv.writer(out)
                writer.writerow(results)



if __name__ == "__main__":
    OPTIONS = argparse.ArgumentParser()
    OPTIONS.add_argument('--run_id', dest='run_id', type=int, default=1)
    OPTIONS.add_argument('--epochs', dest='epochs', type=int, default=500)
    OPTIONS.add_argument('--batch_size', dest='batch_size', type=int, default=32)
    OPTIONS.add_argument('--patience', dest='patience', type=int, default=20)
    OPTIONS.add_argument('--signiture', dest='signiture', type=str, default='')
    OPTIONS.add_argument('--cuda', dest='cuda', type=bool, default=False)
    OPTIONS.add_argument('--model_path', dest='model_path',
                         type=str, default='models')
    OPTIONS.add_argument('--output_path', dest='output_path',
                         type=str, default='results')
    PARAMS = vars(OPTIONS.parse_args())
    main(PARAMS)