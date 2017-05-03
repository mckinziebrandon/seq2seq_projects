"""Tests for various operations done on config (yaml) dictionaries in project."""

import os
import pydoc
import yaml
import logging
import unittest
import tensorflow as tf
from utils import io_utils
import chatbot
import data
from chatbot.globals import DEFAULT_FULL_CONFIG
dir = os.path.dirname(os.path.realpath(__file__))

# Allow user to override config values with command-line args.
# All test_flags with default as None are not accessed unless set.
from main import FLAGS as TEST_FLAGS
TEST_CONFIG_PATH = "configs/test_config.yml"
TEST_FLAGS.config = TEST_CONFIG_PATH
logging.basicConfig(level=logging.INFO)


def update_config(config, **kwargs):
    new_config = {}
    for key in DEFAULT_FULL_CONFIG:
        for new_key in kwargs:
            if new_key in DEFAULT_FULL_CONFIG[key]:
                if new_config.get(key) is None:
                    new_config[key] = {}
                new_config[key][new_key] = kwargs[new_key]
            elif new_key == key:
                new_config[new_key] = kwargs[new_key]
    return {**config, **new_config}


class TestConfig(unittest.TestCase):
    """Test behavior of tf.contrib.rnn after migrating to r1.0."""

    def setUp(self):
        with open('configs/test_config.yml') as f:
            # So we can always reference default vals.
            self.test_config = yaml.load(f)

    def test_path(self):
        conf_path = os.path.abspath('configs/test_config.yml')
        with tf.gfile.GFile(conf_path) as file:
            config_dict = yaml.load(file)

        self.assertIsInstance(config_dict, dict,
                              "Config is type %r" % type(config_dict))

        for key in config_dict['model_params']:
            logging.info(key)
            self.assertIsNotNone(key)

    def test_merge_params(self):
        """Checks how parameters passed to TEST_FLAGS interact with
        parameters from yaml files. Expected behavior is that any
        params in TEST_FLAGS will override those from files, but that
        all values from file will be used if not explicitly passed to
        TEST_FLAGS.
        """

        config = io_utils.parse_config(TEST_FLAGS)

        # ==============================================================
        # Easy tests.
        # ==============================================================

        # Change model in flags and ensure merged config uses that model.
        config = update_config(config, model='ChatBot')
        self.assertEqual(config['model'], 'ChatBot')

        # Also ensure that switching back works too.
        config = update_config(config, model='DynamicBot')
        self.assertEqual(config['model'], 'DynamicBot')

        # Do the same for changing the dataset.
        TEST_FLAGS.dataset = "data.TestData"
        config = update_config(config, dataset='TestData')
        self.assertEqual(config['dataset'], 'TestData')

        # ==============================================================
        # Medium tests.
        # ==============================================================

        # Ensure recursive merging works.
        config = update_config(
            config,
            batch_size=123,
            dropout_prob=0.8)
        logging.info(config)
        self.assertEqual(config['model'], self.test_config['model'])
        self.assertEqual(config['dataset'], self.test_config['dataset'])
        self.assertNotEqual(config['model_params'], self.test_config['model_params'])

    def test_optimize(self):
        """Ensure the new optimize config flag works. 
        
        Right now, 'works' means it correctly determiens the true vocab 
        size, updates it in the config file, and updates any assoc. file names.
        """

        config = io_utils.parse_config(TEST_FLAGS)
        logging.info(config)

        # Manually set vocab size to huge (non-optimal for TestData) value.
        config = io_utils.update_config(config=config, vocab_size=99999)
        self.assertEqual(config['dataset_params']['vocab_size'], 99999)
        self.assertEqual(config['dataset_params']['config_path'],
                         TEST_CONFIG_PATH)

        # Instantiate a new dataset.
        # This where the 'optimize' flag comes into play, since
        # the dataset object is responsible for things like checking
        # data file paths and unique words.
        logging.info("Setting up %s dataset.", config['dataset'])
        logging.info("Passing %r for dataset_params", config['dataset_params'])
        dataset_class = pydoc.locate(config['dataset']) \
                        or getattr(data, config['dataset'])
        dataset = dataset_class(config['dataset_params'])
        self.assertIsInstance(dataset, data.TestData)
        self.assertNotEqual(dataset.vocab_size, 99999)

    def test_update_config(self):
        """Test the new function in io_utils.py"""

        logging.info(os.getcwd())
        config_path = 'configs/test_config.yml'
        config = io_utils.parse_config(config_path)
        self.assertIsInstance(config, dict)
        self.assertTrue('model' in config)
        self.assertTrue('dataset' in config)
        self.assertTrue('dataset_params' in config)
        self.assertTrue('model_params' in config)

        config = io_utils.update_config(
            config_path=config_path,
            return_config=True,
            vocab_size=1234)

        self.assertEqual(config['dataset_params']['vocab_size'], 1234)


if __name__ == '__main__':
    unittest.main()

