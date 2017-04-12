"""Minimal subset of functions/methods from repo needed to run bot on Heroku.
See the main repository for better docs (all from utils and data directory).
"""

import os
import re
import numpy as np
import tensorflow as tf
os.environ['TF_CPP_MIN_LOG_LEVEL']='1'

UNK_ID  = 3
# Regular expressions used to tokenize.
_WORD_SPLIT = re.compile(b"([.,!?\"':;)(])")
_DIGIT_RE   = re.compile(br"\d")


def basic_tokenizer(sentence):
    words = []
    for space_separated_fragment in sentence.strip().split():
        words.extend(_WORD_SPLIT.split(space_separated_fragment))
    return [w for w in words if w]


def sentence_to_token_ids(sentence, vocabulary, normalize_digits=True):
    words = basic_tokenizer(sentence)
    if not normalize_digits:
        return [vocabulary.get(w, UNK_ID) for w in words]
    # Normalize digits by 0 before looking words up in the vocabulary.
    return [vocabulary.get(_DIGIT_RE.sub(b"0", w), UNK_ID) for w in words]


def get_vocab_dicts(vocabulary_path):
    """Returns word_to_idx, idx_to_word dictionaries given vocabulary."""
    if tf.gfile.Exists(vocabulary_path):
        rev_vocab = []
        with tf.gfile.GFile(vocabulary_path, mode="rb") as f:
            rev_vocab.extend(f.readlines())
        rev_vocab = [tf.compat.as_bytes(line.strip()) for line in rev_vocab]
        vocab = dict([(x, y) for (y, x) in enumerate(rev_vocab)])
        return vocab, rev_vocab
    else:
        raise ValueError("Vocabulary file %s not found." % vocabulary_path)


def load_graph(frozen_model_dir):
    """Load frozen tensorflow graph into the default graph.

    Args:
        frozen_model_dir: location of protobuf file containing frozen graph.

    Returns:
        tf.Graph object imported from frozen_model_path.
    """

    # Prase the frozen graph definition into a GraphDef object.
    frozen_file = os.path.join(frozen_model_dir, "frozen_model.pb")
    with tf.gfile.GFile(frozen_file, "rb") as f:
        graph_def = tf.GraphDef()
        graph_def.ParseFromString(f.read())

    # Load the graph def into the default graph and return it.
    with tf.Graph().as_default() as graph:
        tf.import_graph_def(
            graph_def,
            input_map=None,
            return_elements=None,
            op_dict=None,
            producer_op_list=None
        )
    return graph


def unfreeze_bot(frozen_model_path):
    """Restores the frozen graph from file and grabs input/output tensors needed to
    interface with a bot for conversation.

    Args:
        frozen_model_path: location of protobuf file containing frozen graph.

    Returns:
        outputs: tensor that can be run in a session.
    """

    bot_graph   = load_graph(frozen_model_path)
    tensors = {'inputs': bot_graph.get_tensor_by_name('import/input_pipeline/user_input:0'),
               'outputs': bot_graph.get_tensor_by_name('import/outputs:0')}
    return tensors, bot_graph


class FrozenBot:
    """The mouth and ears of a bot that's been serialized."""

    def __init__(self, frozen_model_dir, vocab_size, is_testing=False):
        """
        Args:
            is_testing: (bool) set True for testing (while GPU is busy training). In that case,
                  just use a 'bot' that returns the user's sentence backwards.
        """

        self.is_testing = is_testing
        if not is_testing:
            # Get absolute path to model directory.
            here            = os.path.dirname(os.path.realpath(__file__))
            assets_path     = os.path.join(here, 'static', 'assets')
            abs_model_dir   = os.path.join(assets_path, 'frozen_models', frozen_model_dir)
            # Get bot graph and input/output tensors.
            self.tensor_dict, graph = unfreeze_bot(abs_model_dir)
            self.sess = tf.Session(graph=graph)
            # Make minimal config for retrieving vocab.
            mock_config = {'dataset_params':
                               {'data_dir': abs_model_dir,
                                'vocab_size': vocab_size}}
            self.word_to_idx, self.idx_to_word = self.get_frozen_vocab(mock_config)

    def get_frozen_vocab(self, config):
        """Helper function to get dictionaries between tokens and words."""
        data_dir    = config['dataset_params']['data_dir']
        vocab_size  = config['dataset_params']['vocab_size']
        vocab_paths = {
            'from_vocab': os.path.join(data_dir, 'vocab{}.from'.format(vocab_size)),
            'to_vocab': os.path.join(data_dir, 'vocab{}.to'.format(vocab_size))}
        word_to_idx, _ = get_vocab_dicts(vocabulary_path=vocab_paths['from_vocab'])
        _, idx_to_word = get_vocab_dicts(vocabulary_path=vocab_paths['to_vocab'])
        return word_to_idx, idx_to_word

    def as_words(self, sentence):
        words = " ".join([tf.compat.as_str(self.idx_to_word[i]) for i in sentence])
        words = words.replace(' , ', ', ').replace(' .', '.').replace(' !', '!')
        words = words.replace(" ' ", "'").replace(" ?", "?")
        if len(words) < 2:
            return words
        return words[0].upper() + words[1:]

    def __call__(self, sentence):
        """Outputs response sentence (string) given input (string)."""

        if self.is_testing:
            return sentence[::-1]

        sentence = sentence.strip().lower()
        print('User:', sentence)
        # Convert input sentence to token-ids.
        sentence_tokens = sentence_to_token_ids(
            tf.compat.as_bytes(sentence), self.word_to_idx)
        sentence_tokens = np.array([sentence_tokens[::-1]])
        # Get output sentence from the chatbot.
        fetches = self.tensor_dict['outputs']
        feed_dict={self.tensor_dict['inputs']: sentence_tokens}
        response = self.sess.run(fetches=fetches, feed_dict=feed_dict)
        response = self.as_words(response[0][:-1])
        print("Bot:", response)
        return response

