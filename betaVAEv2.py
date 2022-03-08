import numpy as np
import tensorflow as tf
from tensorflow import keras
from keras import layers
import keras.backend as K

from lib import get_scaled_data


class Sampling(layers.Layer):
    """Uses (z_mean, z_log_var) to sample z (the latent representation)."""

    def call(self, inputs):
        z_mean, z_log_var = inputs
        batch = tf.shape(z_mean)[0]
        dim = tf.shape(z_mean)[1]
        epsilon = tf.keras.backend.random_normal(shape=(batch, dim))
        return z_mean + tf.exp(0.5 * z_log_var) * epsilon

class VariationalAutoencoderV2(keras.Model):
    def __init__(self, network_architecture=None, proba_output=True, beta=1,
                 pretrained_encoder=None, pretrained_decoder=None, **kwargs):
        super(VariationalAutoencoderV2, self).__init__(**kwargs)
        self.latent_dim = network_architecture['n_z']
        self.n_input_nodes = network_architecture['n_input']
        self.network_architecture = network_architecture
        self.proba_output = proba_output
        self.beta = beta
        self.total_loss_tracker = keras.metrics.Mean(name="total_loss")
        self.reconstruction_loss_tracker = keras.metrics.Mean(
            name="reconstruction_loss"
        )
        self.kl_loss_tracker = keras.metrics.Mean(name="kl_loss")
        if pretrained_encoder is not None:
            self.encoder = pretrained_encoder
        else:
            self.encoder = self.create_encoder()
        if pretrained_decoder is not None:
            self.decoder = pretrained_decoder
        else:
            self.decoder = self.create_decoder()

    def create_encoder(self):
        n_hidden_recog_1 = self.network_architecture['n_hidden_recog_1']
        n_hidden_recog_2 = self.network_architecture['n_hidden_recog_2']
        encoder_inputs = keras.Input(shape=self.n_input_nodes)
        h1 = layers.Dense(units=n_hidden_recog_1, activation="relu")(encoder_inputs)
        h2 = layers.Dense(units=n_hidden_recog_2)(h1)
        z_mean = layers.Dense(self.latent_dim, name="z_mean")(h2)
        z_log_var = layers.Dense(self.latent_dim, name="z_log_var")(h2)
        z = Sampling()([z_mean, z_log_var])
        encoder = keras.Model(encoder_inputs, [z_mean, z_log_var, z], name="encoder")
        encoder.summary()
        return encoder

    def create_decoder(self):
        if self.proba_output:
            return self.create_probabalistic_decoder()
        else:
            return self.create_basic_decoder()

    def create_basic_decoder(self):
        n_hidden_gener_1 = self.network_architecture['n_hidden_gener_1']
        n_hidden_gener_2 = self.network_architecture['n_hidden_gener_1']
        latent_inputs = keras.Input(shape=(self.latent_dim,))
        h1 = layers.Dense(n_hidden_gener_1, activation="relu")(latent_inputs)
        h2 = layers.Dense(n_hidden_gener_2, activation="relu")(h1)
        decoder_outputs = layers.Dense(self.n_input_nodes)(h2) # todo in the original implementation we define a distribution on the output
        decoder = keras.Model(latent_inputs, decoder_outputs, name="decoder")
        decoder.summary()
        return decoder

    def create_probabalistic_decoder(self):
        n_hidden_gener_1 = self.network_architecture['n_hidden_gener_1']
        n_hidden_gener_2 = self.network_architecture['n_hidden_gener_1']
        latent_inputs = keras.Input(shape=(self.latent_dim,))
        h1 = layers.Dense(n_hidden_gener_1, activation="relu", name='h1')(latent_inputs)
        h2 = layers.Dense(n_hidden_gener_2, activation="relu", name='h2')(h1)
        x_hat_mean = layers.Dense(self.n_input_nodes, name='x_hat_mean')(h2)
        x_hat_log_sigma_sq = layers.Dense(self.n_input_nodes, name='x_hat_log_sigma_sq')(h2)
        decoder = keras.Model(latent_inputs, [x_hat_mean, x_hat_log_sigma_sq], name="decoder")
        decoder.summary()
        return decoder

    def mvn_neg_ll(self, ytrue, ypreds):
        """Keras implmementation of multivariate Gaussian negative loglikelihood loss function.
        This implementation implies diagonal covariance matrix.

        Parameters
        ----------
        ytrue: tf.tensor of shape [n_samples, n_dims]
            ground truth values
        ypreds: tuple of tf.tensors each of shape [n_samples, n_dims]
            predicted mu and logsigma values (e.g. by your neural network)

        Returns
        -------
        neg_log_likelihood: float
            negative loglikelihood averaged over samples

        This loss can then be used as a target loss for any keras model, e.g.:
            model.compile(loss=mvn_neg_ll, optimizer='Adam')
        """

        mu, log_sigma_sq = ypreds
        sigma = K.sqrt(K.exp(log_sigma_sq))
        logsigma = K.log(sigma)
        n_dims = mu.shape[1]

        sse = -0.5 * K.sum(K.square((ytrue - mu) / sigma),
                           axis=1)  # divide by sigma instead of sigma squared because sigma is inside the square operation
        sigma_trace = -K.sum(logsigma, axis=1)
        log2pi = -0.5 * n_dims * np.log(2 * np.pi)
        log_likelihood = sse + sigma_trace + log2pi

        return K.mean(-log_likelihood)

    @property
    def metrics(self):
        return [
            self.total_loss_tracker,
            self.reconstruction_loss_tracker,
            self.kl_loss_tracker,
        ]

    def train_step(self, data):
        x, y = data
        with tf.GradientTape() as tape:
            z_mean, z_log_var, z = self.encoder(x)
            if self.proba_output:
                # output = self.decoder(z)
                # tf.print(output[0].shape)
                # tf.print(len(output))
                x_hat_mean, x_hat_log_sigma_sq = self.decoder(z)
                reconstruction_loss = self.mvn_neg_ll(y, (x_hat_mean, x_hat_log_sigma_sq))
                # reconstruction_loss = tfp.distributions.Normal(loc=x_hat_mean, scale=x_hat_log_sigma_sq).log_prob(y) # note that the scale parameter is sigma not sigma squared
            else:
                reconstruction = self.decoder(z)
                reconstruction_loss = tf.reduce_mean(
                    tf.reduce_mean(
                        keras.losses.mean_squared_error(y, reconstruction)
                    )
                )

            kl_loss = -0.5 * (1 + z_log_var - tf.square(z_mean) - tf.exp(z_log_var)) # identical form to the other implementation
            kl_loss = tf.reduce_mean(tf.reduce_sum(kl_loss, axis=1))
            total_loss = reconstruction_loss + self.beta * kl_loss
        grads = tape.gradient(total_loss, self.trainable_weights)
        self.optimizer.apply_gradients(zip(grads, self.trainable_weights))
        self.total_loss_tracker.update_state(total_loss)
        self.reconstruction_loss_tracker.update_state(reconstruction_loss)
        self.kl_loss_tracker.update_state(kl_loss)
        return {
            "loss": self.total_loss_tracker.result(),
            "reconstruction_loss": self.reconstruction_loss_tracker.result(),
            "kl_loss": self.kl_loss_tracker.result(),
        }
    def predict(self, x):
        z_mean, z_log_var, z = self.encoder(x)
        if self.proba_output:
            x_hat_mean, x_hat_log_sigma_sq = self.decoder(z_mean)
            return x_hat_mean
        else:
            return self.decoder(z_mean)


if __name__=="__main__":
    physical_devices = tf.config.list_physical_devices('GPU')
    tf.config.set_visible_devices(physical_devices[-1], 'GPU')
    logical_devices = tf.config.list_logical_devices('GPU')
    print(logical_devices)
    data, data_missing = get_scaled_data()
    n_row = data.shape[1]
    network_architecture = \
        dict(n_hidden_recog_1=6000,  # 1st layer encoder neurons
             n_hidden_recog_2=2000,  # 2nd layer encoder neurons
             n_hidden_gener_1=2000,  # 1st layer decoder neurons
             n_hidden_gener_2=6000,  # 2nd layer decoder neurons
             n_input=n_row,  # data input size
             n_z=200)  # dimensionality of latent space

    vae = VariationalAutoencoderV2(network_architecture=network_architecture)
    vae.compile(optimizer=keras.optimizers.Adam(learning_rate=0.0001, clipnorm=1.0))
    vae.fit(x=data_missing, y=data, epochs=1000, batch_size=256)