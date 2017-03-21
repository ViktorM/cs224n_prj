import os

import keras


class MyModelCheckpoint(keras.callbacks.Callback):
    def __init__(self, dir, weights_name, epoch_period=1, model_id=None):
        self.path_begin = os.path.join(dir, weights_name)
        self.model_id = model_id
        self.period = max(1, epoch_period)
        self.log_file = open(os.path.join(dir, 'epoch_history_{0}.log'.format(self.model_id)), 'w')

    def on_epoch_end(self, epoch, logs=None):
        # we want 1-indexed epoch in output
        epoch += 1
        if 'val_loss' in logs:
            self.log_file.write('Epoch {0}\tTrain {1}\t Val {2}\n'.format(epoch, logs['loss'], logs['val_loss']))
        else:
            self.log_file.write('Epoch {0}\t Train {1}\n'.format(epoch, logs['loss']))

        if epoch % self.period == 0:
            filename = '{}_{:03}_{}.hdf5'.format(self.path_begin, epoch, self.model_id)
            self.model.save_weights(filename)

    def on_train_end(self, logs=None):
        self.log_file.close()


class BestModelCheckpoint(keras.callbacks.Callback):
    def __init__(self, dir, weights_name, epoch_period=1, model_id=None):
        self.path_begin = os.path.join(dir, weights_name)
        self.model_id = model_id
        self.period = max(1, epoch_period)
        self.log_file = open(os.path.join(dir, 'epoch_history_{0}.log'.format(self.model_id)), 'w')
        self.best_loss = 1.0e6
        self.best_epoch = -1

    def on_epoch_end(self, epoch, logs=None):
        # we want 1-indexed epoch in output
        epoch += 1
        if 'val_loss' in logs:
            if (epoch > self.period) and (logs['val_loss'] < self.best_loss):
                self.best_loss = logs['val_loss']
                self.best_epoch = epoch
                self.log_file.write('New best result achieved!\n')
                filename = 'best_{}_{:03}.hdf5'.format(self.model_id, epoch)
                self.model.save_weights(filename)
            self.log_file.write('Epoch {0}\tTrain {1}\t Val {2}\n'.format(epoch, logs['loss'], logs['val_loss']))

        else:
            self.log_file.write('Epoch {0}\t Train {1}\n'.format(epoch, logs['loss']))

        if epoch % self.period == 0:
            filename = '{}_{:03}_{}.hdf5'.format(self.path_begin, epoch, self.model_id)
            self.model.save_weights(filename)

    def on_train_end(self, logs=None):
        self.log_file.close()
