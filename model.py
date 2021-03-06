import argparse
import json
import random
import os
import datetime
import h5py
import keras
import numpy as np
import tensorflow as tf

from keras.applications.vgg16 import VGG16
from keras.applications.vgg19 import VGG19
from keras.applications.resnet50 import ResNet50
from keras.applications.inception_v3 import InceptionV3
from keras.applications.xception import Xception
from keras.applications.resnet50 import ResNet50

from keras.engine import Input
from keras.layers import GlobalMaxPooling2D, GRU, LSTM, Dense, Activation, Embedding, TimeDistributed, RepeatVector, \
    Bidirectional
from keras.layers.normalization import BatchNormalization
from keras.models import Sequential, Merge, Model

from model_checkpoints import MyModelCheckpoint, BestModelCheckpoint
from settings_keeper import SettingsKeeper
from squeezenet.squeezenet import get_squeezenet


def create_image_model_resnet50(images_shape, repeat_count):
    print('Using ResNet50')
    inputs = Input(shape=images_shape)

    visual_model = ResNet50(weights='imagenet', include_top=False, input_tensor=inputs)

    x = visual_model(inputs)
    x = GlobalMaxPooling2D()(x)
    x = RepeatVector(repeat_count)(x)

    return Model(inputs, x, 'image_model')


def create_image_model_squeezenet(images_shape, repeat_count):
    print('Using SqueezeNet')
    inputs = Input(shape=images_shape)

    visual_model = get_squeezenet(1000, dim_ordering='tf', include_top=False)
    # visual_model.load_weights('squeezenet/model/squeezenet_weights_tf_dim_ordering_tf_kernels.h5')

    x = visual_model(inputs)
    x = GlobalMaxPooling2D()(x)
    x = RepeatVector(repeat_count)(x)

    return Model(inputs, x, 'image_model')


def create_image_model_xception(images_shape, repeat_count):
    print('Using Xception')
    inputs = Input(shape=images_shape)

    visual_model = Xception(weights='imagenet', include_top=False, input_tensor=inputs)

    x = visual_model(inputs)
    x = GlobalMaxPooling2D()(x)
    x = RepeatVector(repeat_count)(x)
    return Model(inputs, x, 'image_model')


def create_sentence_model(dict_size, sentence_len, pretrained_emb, gru_size=128):
    sentence_model = Sequential()

    if pretrained_emb is not None:
        # read initial matrix
        word_dim = pretrained_emb.shape[0]
        embed_dim = pretrained_emb.shape[1]
        sentence_model.add(Embedding(word_dim, embed_dim, input_length=sentence_len, mask_zero=True,
                                     weights=[pretrained_emb]))
    else:
        # + 1 to respect masking
        sentence_model.add(Embedding(dict_size + 1, 512, input_length=sentence_len, mask_zero=True))

    sentence_model.add(GRU(output_dim=gru_size, return_sequences=True, dropout_U=0.2, dropout_W=0.2))
    sentence_model.add(TimeDistributed(Dense(gru_size)))

    return sentence_model


def create_sentence_model2(dict_size, sentence_len, pretrained_emb, gru_size=128):
    sentence_model = Sequential()

    if pretrained_emb is not None:
        # read initial matrix
        word_dim = pretrained_emb.shape[0]
        embed_dim = pretrained_emb.shape[1]
        sentence_model.add(Embedding(word_dim, embed_dim, input_length=sentence_len, mask_zero=True,
                                     weights=[pretrained_emb]))
    else:
        # + 1 to respect masking
        sentence_model.add(Embedding(dict_size + 1, 512, input_length=sentence_len, mask_zero=True))

    sentence_model.add(GRU(output_dim=gru_size, return_sequences=True, dropout_U=0.2, dropout_W=0.2))
    sentence_model.add(GRU(output_dim=gru_size, return_sequences=True, dropout_U=0.2, dropout_W=0.2))
    sentence_model.add(TimeDistributed(Dense(gru_size)))

    return sentence_model


def create_sentence_model_bn(dict_size, sentence_len, pretrained_emb):
    sentence_model = Sequential()

    if pretrained_emb is not None:
        # read initial matrix
        word_dim = pretrained_emb.shape[0]
        embed_dim = pretrained_emb.shape[1]
        sentence_model.add(Embedding(word_dim, embed_dim, input_length=sentence_len, mask_zero=True,
                                     weights=[pretrained_emb]))
    else:
        # + 1 to respect masking
        sentence_model.add(Embedding(dict_size + 1, 512, input_length=sentence_len, mask_zero=True))

    sentence_model.add(BatchNormalization())
    sentence_model.add(GRU(output_dim=128, return_sequences=True, dropout_U=0.0, dropout_W=0.0))
    sentence_model.add(BatchNormalization())
    sentence_model.add(TimeDistributed(Dense(128)))
    #    sentence_model.add(BatchNormalization())

    return sentence_model


def create_sentence_model_bidirectional(dict_size, sentence_len, pretrained_emb):
    sentence_model = Sequential()

    if pretrained_emb is not None:
        # read initial matrix
        word_dim = pretrained_emb.shape[0]
        embed_dim = pretrained_emb.shape[1]
        sentence_model.add(Embedding(word_dim, embed_dim, input_length=sentence_len, mask_zero=True,
                                     weights=[pretrained_emb]))
    else:
        # + 1 to respect masking
        sentence_model.add(Embedding(dict_size + 1, 512, input_length=sentence_len, mask_zero=True))

    sentence_model.add(Bidirectional(GRU(output_dim=128, return_sequences=True, dropout_U=0.2, dropout_W=0.2),
                                     merge_mode='concat'))
    sentence_model.add(TimeDistributed(Dense(256)))

    return sentence_model


def create_sentence_model_lstm(dict_size, sentence_len, pretrained_emb):
    sentence_model = Sequential()

    if pretrained_emb is not None:
        # read initial matrix
        word_dim = pretrained_emb.shape[0]
        embed_dim = pretrained_emb.shape[1]
        sentence_model.add(Embedding(word_dim, embed_dim, input_length=sentence_len, mask_zero=True,
                                     weights=[pretrained_emb]))
    else:
        # + 1 to respect masking
        sentence_model.add(Embedding(dict_size + 1, 512, input_length=sentence_len, mask_zero=True))

    sentence_model.add(LSTM(output_dim=128, return_sequences=True, dropout_U=0.2, dropout_W=0.2))
    sentence_model.add(TimeDistributed(Dense(128)))

    return sentence_model


def create_optimizer(settings):
    print('Creating optimizer: {0}'.format(settings.optimizer))
    if settings.optimizer == 'adam':
        return keras.optimizers.Adam(lr=settings.learn_rate, beta_1=settings.beta_1, beta_2=settings.beta_2,
                                     epsilon=settings.epsilon, decay=settings.decay)
    if settings.optimizer == 'nadam':
        return keras.optimizers.Nadam(lr=settings.learn_rate, beta_1=settings.beta_1, beta_2=settings.beta_2,
                                      epsilon=settings.epsilon, schedule_decay=settings.schedule_decay)


def create_glorot_int_matrix(shape):
    sum_dims = np.sum(shape)
    e = np.sqrt(6.0 / sum_dims)
    return np.random.uniform(-e, e, shape)


def addPredictionLayers(model, dict_size, settings):
    if settings.token_freq is not None:
        # skipping 0 index as it is used for masking
        bias_init = np.array([1.0 * cur_freq for cur_freq in settings.token_freq[1:]])
        bias_init /= np.sum(bias_init)
        bias_init = np.log(bias_init)
        bias_init -= np.max(bias_init)
        matrix_init = create_glorot_int_matrix((model.output_shape[1], dict_size))
        model.add(Dense(dict_size, weights=[matrix_init, bias_init]))
        print('Softmax biases have been have been intialized by log of words frequencies.')
    else:
        model.add(Dense(dict_size))
        print('Softmax biases have been intialized by 0.')
    model.add(Activation('softmax'))


def create_default_model(images_shape, dict_size, sentence_len, settings, pretrained_emb):
    # input (None, 224, 224, 3), outputs (None, sentence_len, 512)
    image_model = create_image_model_resnet50(images_shape, sentence_len)

    # outputs (None, sentence_len, 128)
    sentence_model = create_sentence_model(dict_size, sentence_len, pretrained_emb)

    combined_model = Sequential()
    combined_model.add(Merge([image_model, sentence_model], mode='concat', concat_axis=-1))
    combined_model.add(GRU(256, return_sequences=False, dropout_U=0.2, dropout_W=0.2))

    addPredictionLayers(combined_model, dict_size, settings)

    # input words are 1-indexed and 0 index is used for masking!
    # but result words are 0-indexed and will go into [0, ..., dict_size-1] !!!

    combined_model.compile(loss='sparse_categorical_crossentropy', optimizer=create_optimizer(settings))
    return combined_model


def create_GRU_large_model(images_shape, dict_size, sentence_len, settings, pretrained_emb):
    # input (None, 224, 224, 3), outputs (None, sentence_len, 512)
    image_model = create_image_model_resnet50(images_shape, sentence_len)

    # outputs (None, sentence_len, 128)
    sentence_model = create_sentence_model(dict_size, sentence_len, pretrained_emb, 160)

    combined_model = Sequential()
    combined_model.add(Merge([image_model, sentence_model], mode='concat', concat_axis=-1))
    combined_model.add(GRU(320, return_sequences=False, dropout_U=0.25, dropout_W=0.25))

    addPredictionLayers(combined_model, dict_size, settings)

    # input words are 1-indexed and 0 index is used for masking!
    # but result words are 0-indexed and will go into [0, ..., dict_size-1] !!!

    combined_model.compile(loss='sparse_categorical_crossentropy', optimizer=create_optimizer(settings))
    return combined_model


def create_GRU_deep_model(images_shape, dict_size, sentence_len, settings, pretrained_emb):
    # input (None, 224, 224, 3), outputs (None, sentence_len, 512)
    image_model = create_image_model_resnet50(images_shape, sentence_len)

    # outputs (None, sentence_len, 128)
    sentence_model = create_sentence_model2(dict_size, sentence_len, pretrained_emb)

    combined_model = Sequential()
    combined_model.add(Merge([image_model, sentence_model], mode='concat', concat_axis=-1))
    combined_model.add(GRU(256, return_sequences=False, dropout_U=0.2, dropout_W=0.2))

    addPredictionLayers(combined_model, dict_size, settings)

    # input words are 1-indexed and 0 index is used for masking!
    # but result words are 0-indexed and will go into [0, ..., dict_size-1] !!!

    combined_model.compile(loss='sparse_categorical_crossentropy', optimizer=create_optimizer(settings))
    return combined_model


def create_batchnorm_model(images_shape, dict_size, sentence_len, settings, pretrained_emb):
    # input (None, 224, 224, 3), outputs (None, sentence_len, 512)
    image_model = create_image_model_resnet50(images_shape, sentence_len)

    # outputs (None, sentence_len, 128)
    sentence_model = create_sentence_model_bn(dict_size, sentence_len, pretrained_emb)

    combined_model = Sequential()
    combined_model.add(Merge([image_model, sentence_model], mode='concat', concat_axis=-1))
    combined_model.add(BatchNormalization())
    combined_model.add(GRU(256, return_sequences=False, dropout_U=0.0, dropout_W=0.0))
    combined_model.add(BatchNormalization())

    addPredictionLayers(combined_model, dict_size, settings)

    # input words are 1-indexed and 0 index is used for masking!
    # but result words are 0-indexed and will go into [0, ..., dict_size-1] !!!

    combined_model.compile(loss='sparse_categorical_crossentropy', optimizer=create_optimizer(settings))
    return combined_model


def create_GRU_BIDIR_model(images_shape, dict_size, sentence_len, settings, pretrained_emb):
    # input (None, 224, 224, 3), outputs (None, sentence_len, 512)
    image_model = create_image_model_resnet50(images_shape, sentence_len)

    # outputs (None, sentence_len, 128)
    sentence_model = create_sentence_model_bidirectional(dict_size, sentence_len, pretrained_emb)

    combined_model = Sequential()
    combined_model.add(Merge([image_model, sentence_model], mode='concat', concat_axis=-1))
    combined_model.add(GRU(256, return_sequences=False, dropout_U=0.2, dropout_W=0.2))

    addPredictionLayers(combined_model, dict_size, settings)

    # input words are 1-indexed and 0 index is used for masking!
    # but result words are 0-indexed and will go into [0, ..., dict_size-1] !!!

    combined_model.compile(loss='sparse_categorical_crossentropy', optimizer=create_optimizer(settings))
    return combined_model


def create_GRU_BIDIR_2_model(images_shape, dict_size, sentence_len, settings, pretrained_emb):
    # input (None, 224, 224, 3), outputs (None, sentence_len, 512)
    image_model = create_image_model_resnet50(images_shape, sentence_len)

    # outputs (None, sentence_len, 128)
    sentence_model = create_sentence_model_bidirectional(dict_size, sentence_len, pretrained_emb)

    combined_model = Sequential()
    combined_model.add(Merge([image_model, sentence_model], mode='concat', concat_axis=-1))
    combined_model.add(Bidirectional(GRU(160, return_sequences=False, dropout_U=0.25, dropout_W=0.25),
                                     merge_mode='concat'))

    addPredictionLayers(combined_model, dict_size, settings)

    # input words are 1-indexed and 0 index is used for masking!
    # but result words are 0-indexed and will go into [0, ..., dict_size-1] !!!

    combined_model.compile(loss='sparse_categorical_crossentropy', optimizer=create_optimizer(settings))
    return combined_model


def create_GRU_2_model(images_shape, dict_size, sentence_len, settings, pretrained_emb):
    # input (None, 224, 224, 3), outputs (None, sentence_len, 512)
    image_model = create_image_model_resnet50(images_shape, sentence_len)

    # outputs (None, sentence_len, 128)
    sentence_model = create_sentence_model(dict_size, sentence_len, pretrained_emb)

    combined_model = Sequential()
    combined_model.add(Merge([image_model, sentence_model], mode='concat', concat_axis=-1))
    combined_model.add(GRU(256, return_sequences=True, dropout_U=0.25, dropout_W=0.25))
    combined_model.add(GRU(256, return_sequences=False, dropout_U=0.25, dropout_W=0.25))

    addPredictionLayers(combined_model, dict_size, settings)

    # input words are 1-indexed and 0 index is used for masking!
    # but result words are 0-indexed and will go into [0, ..., dict_size-1] !!!

    combined_model.compile(loss='sparse_categorical_crossentropy', optimizer=create_optimizer(settings))
    return combined_model


def create_GRU_squeezenet_model(images_shape, dict_size, sentence_len, settings, pretrained_emb):
    image_model = create_image_model_squeezenet(images_shape, sentence_len)

    sentence_model = create_sentence_model(dict_size, sentence_len, pretrained_emb)

    combined_model = Sequential()
    combined_model.add(Merge([image_model, sentence_model], mode='concat', concat_axis=-1))
    combined_model.add(GRU(256, return_sequences=False, dropout_U=0.2, dropout_W=0.2))

    addPredictionLayers(combined_model, dict_size, settings)

    # input words are 1-indexed and 0 index is used for masking!
    # but result words are 0-indexed and will go into [0, ..., dict_size-1] !!!

    combined_model.compile(loss='sparse_categorical_crossentropy', optimizer=create_optimizer(settings))
    return combined_model


def create_GRU_xception_model(images_shape, dict_size, sentence_len, settings, pretrained_emb):
    image_model = create_image_model_xception(images_shape, sentence_len)

    sentence_model = create_sentence_model(dict_size, sentence_len, pretrained_emb)

    combined_model = Sequential()
    combined_model.add(Merge([image_model, sentence_model], mode='concat', concat_axis=-1))
    combined_model.add(GRU(256, return_sequences=False, dropout_U=0.2, dropout_W=0.2))

    addPredictionLayers(combined_model, dict_size, settings)

    # input words are 1-indexed and 0 index is used for masking!
    # but result words are 0-indexed and will go into [0, ..., dict_size-1] !!!

    combined_model.compile(loss='sparse_categorical_crossentropy', optimizer=create_optimizer(settings))
    return combined_model


def create_GRU_stack_model(images_shape, dict_size, sentence_len, settings, pretrained_emb):
    # input (None, 224, 224, 3), outputs (None, sentence_len, 512)
    image_model = create_image_model_resnet50(images_shape, sentence_len)

    # outputs (None, sentence_len, 128)
    sentence_model = create_sentence_model(dict_size, sentence_len, pretrained_emb, 160)

    combined_model = Sequential()
    combined_model.add(Merge([image_model, sentence_model], mode='concat', concat_axis=-1))
    combined_model.add(GRU(160, return_sequences=True, dropout_U=0.25, dropout_W=0.25))

    combined_model2 = Sequential()
    combined_model2.add(Merge([image_model, combined_model], mode='concat', concat_axis=-1))
    combined_model2.add(GRU(256, return_sequences=False, dropout_U=0.25, dropout_W=0.25))

    addPredictionLayers(combined_model2, dict_size, settings)

    # input words are 1-indexed and 0 index is used for masking!
    # but result words are 0-indexed and will go into [0, ..., dict_size-1] !!!

    combined_model2.compile(loss='sparse_categorical_crossentropy', optimizer=create_optimizer(settings))
    return combined_model2


def create_lstm_nadam_model(images_shape, dict_size, sentence_len, settings, pretrained_emb):
    # input (None, 224, 224, 3), outputs (None, sentence_len, 512)
    image_model = create_image_model_resnet50(images_shape, sentence_len)

    # outputs (None, sentence_len, 128)
    sentence_model = create_sentence_model_lstm(dict_size, sentence_len, pretrained_emb)

    combined_model = Sequential()
    combined_model.add(Merge([image_model, sentence_model], mode='concat', concat_axis=-1))

    combined_model.add(LSTM(256, return_sequences=False, dropout_U=0.1, dropout_W=0.2))
    #    combined_model.add(LSTM(256, return_sequences=False))

    addPredictionLayers(combined_model, dict_size, settings)

    # input words are 1-indexed and 0 index is used for masking!
    # but result words are 0-indexed and will go into [0, ..., dict_size-1] !!!

    combined_model.compile(loss='sparse_categorical_crossentropy', optimizer=create_optimizer(settings))
    return combined_model


def create_model(images_shape, dict_size, sentence_len, settings):
    model_creators = {
        'default_model': create_default_model,
        'LSTM_model': create_lstm_nadam_model,

		'GRU_dropout': create_default_model,
        'GRU_batch_norm': create_batchnorm_model,

        'GRU_1_05': create_default_model,
        'GRU_1_04': create_default_model,
        'GRU_1_03': create_default_model,
        'GRU_2_03': create_default_model,
        'GRU_5_03': create_default_model,
        'GRU_5_04': create_default_model,

        'GRU_DEEP': create_GRU_deep_model,
        'GRU_LARGE': create_GRU_large_model,

        'GRU_2': create_GRU_2_model,
        'GRU_stacked': create_GRU_stack_model,
        'GRU_BIDIR': create_GRU_BIDIR_model,
        'GRU_BIDIR_2': create_GRU_BIDIR_2_model,

        'GRU_squeezenet': create_GRU_squeezenet_model,
        'GRU_xception': create_GRU_xception_model,

        'GRU_1_03_glove': create_default_model,

        'GRU_adam_1_03': create_default_model,
    }

    print('Using model "{0}"'.format(settings.model))

    # Pretrained embeddings
    if settings.pretrained_word_vectors_file:
        print('Loading word_vectors file "{0}"'.format(settings.pretrained_word_vectors_file))
        pretrained_emb = np.load(settings.pretrained_word_vectors_file)
    else:
        pretrained_emb = None

    model_creator = model_creators[settings.model]
    return model_creator(images_shape, dict_size, sentence_len, settings, pretrained_emb)


def prepare_batch(sentences_dset, sentences_next_dset, sent_to_img_dset, images_dset, batch_size):
    num_sentences = sentences_dset.shape[0]
    assert (num_sentences == sentences_next_dset.shape[0])

    while 1:
        indices = np.random.randint(num_sentences, size=batch_size)
        sentences_data = np.array([sentences_dset[ind] for ind in indices])
        images_data = np.array([images_dset[sent_to_img_dset[ind]] for ind in indices])

        # input words are 1-indexed and 0 index is used for masking!
        # but result words are 0-indexed and will go into [0, ..., dict_size-1] !!!
        truth_data = np.array([sentences_next_dset[ind] - 1 for ind in indices])

        yield [images_data, sentences_data], truth_data


def train_model(h5_images_train=None, h5_text_train=None, dict_size_train=None,
                h5_images_val=None, h5_text_val=None, settings=None):
    # Train
    images_train = h5_images_train['images']
    sent_to_img_train = h5_text_train['sentences_to_img']
    sentences_train = h5_text_train['sentences']
    sentences_next_train = h5_text_train['sentences_next']

    # Val
    val_samples = settings.val_samples
    if h5_images_val and h5_text_val and val_samples:
        images_val = h5_images_val['images']
        sent_to_img_val = h5_text_val['sentences_to_img']
        sentences_val = h5_text_val['sentences']
        sentences_next_val = h5_text_val['sentences_next']

        # initialize val generator
        val_stream = prepare_batch(sentences_val, sentences_next_val, sent_to_img_val, images_val, settings.batch_size)
    else:
        val_stream = None
        val_samples = None

    sentence_len = len(sentences_train[0])
    image_shape = images_train.shape[1:]

    model = create_model(image_shape, dict_size_train, sentence_len, settings)
    if settings.weights is not None:
        model.load_weights(settings.weights)
        print('Using start weights: "{}"'.format(settings.weights))

    tb = keras.callbacks.TensorBoard(log_dir=settings.model_output_dir, histogram_freq=1, write_images=True,
                                     write_graph=True)
    cp = BestModelCheckpoint(settings.model_output_dir, settings.model, settings.weight_save_epoch_period,
                             model_id=settings.model_id)

    # Initialize train generator
    train_stream = prepare_batch(sentences_train, sentences_next_train, sent_to_img_train, images_train,
                                 settings.batch_size)

    model.fit_generator(generator=train_stream,
                        samples_per_epoch=settings.samples_per_epoch,
                        validation_data=val_stream,
                        nb_val_samples=val_samples,
                        nb_epoch=settings.num_epoch,
                        callbacks=[tb, cp])


def main_func():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model_id',
                        default='{0:%y_%m_%d_%H_%M_%S}'.format(datetime.datetime.now()), type=str)
    parser.add_argument('--cuda_devices',
                        default=None)
    parser.add_argument('--weights',
                        default=None)
    parser.add_argument('--model',
                        default='default_model')

    args = parser.parse_args()

    settings_ini_section_list = ['model', args.model]
    settings = SettingsKeeper()
    settings.add_ini_file('settings.ini', settings_ini_section_list)
    if os.path.isfile('user_settings.ini'):
        settings.add_ini_file('user_settings.ini', settings_ini_section_list, False)
    settings.add_parsed_arguments(args)

    if settings.cuda_devices is not None:
        os.environ['CUDA_VISIBLE_DEVICES'] = settings.cuda_devices

    random.seed(settings.seed)
    np.random.seed(settings.seed)
    tf.set_random_seed(settings.seed)

    # Adding model name to the beginning of the result files
    # settings.model_id = '{0}_{1}'.format(settings.model, settings.model_id)

    # Train data
    id_to_word_train = os.path.join(settings.preprocessed_train, 'id_to_word.json')
    with open(id_to_word_train, 'r') as f:
        dict_size_train = len(json.load(f))

    preprocessed_images_train = os.path.join(settings.preprocessed_train, 'preprocessed_images.h5')
    preprocessed_text_train = os.path.join(settings.preprocessed_train, 'preprocessed_text.h5')

    preprocessed_token_freq_path = os.path.join(settings.preprocessed_train, 'id_to_freq.json')
    if os.path.exists(preprocessed_token_freq_path):
        with open(preprocessed_token_freq_path, 'r') as f:
            loaded_preprocessed_token_freq = json.load(f)
            token_freq_total = dict_size_train + 1

            preprocessed_token_freq = [0]
            for ind in range(1, token_freq_total):
                token_freq = loaded_preprocessed_token_freq.get(str(ind), 0)
                assert (token_freq > 0)
                preprocessed_token_freq.append(token_freq)
    else:
        preprocessed_token_freq = None
        print('Softmax biases are initialized with zeros.')
    settings.add_key_value('token_freq', preprocessed_token_freq)

    # Val data
    if settings.preprocessed_val is not None:
        preprocessed_images_val = os.path.join(settings.preprocessed_val, 'preprocessed_images.h5')
        preprocessed_text_val = os.path.join(settings.preprocessed_val, 'preprocessed_text.h5')

        h5_images_val = h5py.File(preprocessed_images_val, 'r')
        h5_text_val = h5py.File(preprocessed_text_val, 'r')
    else:
        h5_images_val, h5_text_val = None, None

    with h5py.File(preprocessed_images_train, 'r') as h5_images_train, \
            h5py.File(preprocessed_text_train, 'r') as h5_text_train:

        train_model(h5_images_train=h5_images_train, h5_text_train=h5_text_train, dict_size_train=dict_size_train,
                    # train data
                    h5_images_val=h5_images_val, h5_text_val=h5_text_val,
                    settings=settings)

    if h5_text_val and h5_images_val:
        h5_text_val.close()
        h5_images_val.close()


if __name__ == '__main__':
    main_func()
