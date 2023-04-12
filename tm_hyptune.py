import numpy as np
from sklearn.datasets import fetch_20newsgroups
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from tmu.models.autoencoder.autoencoder import TMAutoEncoder
import pandas as pd
from time import time

# Load data
categories = ['alt.atheism', 'soc.religion.christian', 'talk.religion.misc']
print("fetching training data \n")
data_train = fetch_20newsgroups(
    subset='train', categories=categories, shuffle=False)
print("fetching test data \n")
data_test = fetch_20newsgroups(
    subset='test', categories=categories, shuffle=False)


# Pre-process data
for data_set in [data_train, data_test]:
    temp = []
    for i in range(len(data_set.data)):
        # Remove all data before and including the line which includes an email address
        a = data_set.data[i].splitlines()
        for j in range(len(a)):
            if 'Lines:' in a[j]:
                a = a[j+1:]
                break
        data_set.data[i] = ' '.join(a)
        data_set.data[i] = data_set.data[i].replace(",", " ,")
        data_set.data[i] = data_set.data[i].replace('!', ' !')
        data_set.data[i] = data_set.data[i].replace('?', ' ?')
        data_set.data[i] = data_set.data[i].split('.')

    for doc in data_set.data:
        for sentence in doc:
            if len(sentence) < 5:
                continue
            if len(sentence.split()) < 5:
                continue
            sentence = sentence.strip()
            temp.append(sentence)

    data_set.data = temp


# Function to index a sentence based on a keyword
def index_sentence(sentence, keyword):
    words = sentence.split()
    index = {}
    found_keyword = False
    for i in range(len(words)):
        if words[i] == keyword:
            found_keyword = True
        if found_keyword:
            index[words[i]] = i - len(words)
        else:
            index[words[i]] = i
    return index


# Create a count vectorizer
parsed_data_train = []
for i in range(len(data_train.data)):
    a = data_train.data[i].split()
    parsed_data_train.append(a)

parsed_data_test = []
for i in range(len(data_test.data)):
    a = data_test.data[i].split()
    parsed_data_test.append(a)


def tokenizer(s):
    return s


count_vect = CountVectorizer(tokenizer=tokenizer, lowercase=False, binary=True)

X_train_counts = count_vect.fit_transform(parsed_data_train)
feature_names = count_vect.get_feature_names_out()
number_of_features = count_vect.get_feature_names_out().shape[0]

X_test_counts = count_vect.transform(parsed_data_test)

# Create Hyperparameter vectors
examples_max = 1000
margin_max = 500
clause_max = 215
specificity_max = 20.0
accumulation_max = 50
steps = 32

examples_vector = [100]
margin_vector = [50]
clause_vector = [15]
# Setting specificity to 1 makes the epochs take 400+ seconds
specificity_vector = [5.0]
accumulation_vector = [1]


for i in range(steps):
    examples_vector.append(
        examples_vector[i] + (examples_max - examples_vector[0]) // steps)
    margin_vector.append(
        margin_vector[i] + (margin_max - margin_vector[0]) // steps)
    clause_vector.append(
        clause_vector[i] + (clause_max - clause_vector[0]) // steps)
    specificity_vector.append(
        specificity_vector[i] + (specificity_max - specificity_vector[0]) / steps)
    accumulation_vector.append(
        accumulation_vector[i] + (accumulation_max - accumulation_vector[0]) // steps)

# Set Hyperparameters

clause_weight_threshold = 0
num_examples = 500
clauses = 50
# How many votes needed for action
margin = 80
# Forget value
specificity = 10.0
accumulation = 25
epochs = 15

# Create a Tsetlin Machine Autoencoder
target_words = ['Jesus', 'Christ',
                'accept', 'trust', 'faith', 'religious', 'person', 'human', 'God', 'atheists']

output_active = np.empty(len(target_words), dtype=np.uint32)
for i in range(len(target_words)):
    target_word = target_words[i]

    target_id = count_vect.vocabulary_[target_word]
    output_active[i] = target_id

df = pd.DataFrame(columns=['words', 'clauses', 'examples',
                  'margin', 'clause', 'specificity', 'accumulation'])
df.to_csv('results.csv', index=False, header=False, mode='w')


def train(example_index, margin_index, clause_index, specificity_index, accumulation_index):
    enc = TMAutoEncoder(number_of_clauses=clause_vector[clause_index], T=margin_vector[margin_index],
                        s=specificity_vector[specificity_index], output_active=output_active, accumulation=accumulation_vector[accumulation_index], feature_negation=False, platform='CPU', output_balancing=True)
    print(
        f"hyperparameters: \n examples: {examples_vector[example_index]} margin: {margin_vector[margin_index]} clauses: {clause_vector[clause_index]} specificity: {specificity_vector[specificity_index]} accumulation: {accumulation_vector[accumulation_index]}")

    # Train the Tsetlin Machine Autoencoder
    print("Starting training \n")
    for e in range(epochs):
        start_training = time()
        enc.fit(X_train_counts,
                number_of_examples=examples_vector[example_index])
        stop_training = time()

        profile = np.empty((len(target_words), clause_vector[clause_index]))
        precision = []
        recall = []
        for i in range(len(target_words)):
            precision.append(enc.clause_precision(
                i, True, X_train_counts, number_of_examples=examples_vector[example_index]))
            recall.append(enc.clause_recall(
                i, True, X_train_counts, number_of_examples=examples_vector[example_index]))
            weights = enc.get_weights(i)
            profile[i, :] = np.where(
                weights >= clause_weight_threshold, weights, 0)

        print("Epoch #%d" % (e+1))

        if e == epochs - 1:
            print("Precision: %s" % precision)
            print("Recall: %s \n" % recall)
            print("Clauses\n")
            """
            clause_result = []
            for j in range(clause_vector[clause_index]):
                print("Clause #%d " % (j), end=' ')
                for i in range(len(target_words)):
                    print("%s: W%d:P%.2f:R%.2f " % (target_words[i], enc.get_weight(
                        i, j), precision[i][j], recall[i][j]), end=' ')

                l = []
                for k in range(enc.clause_bank.number_of_literals):
                    if enc.get_ta_action(j, k) == 1:
                        if k < enc.clause_bank.number_of_features:
                            l.append("%s(%d)" % (
                                feature_names[k], enc.clause_bank.get_ta_state(j, k)))
                        else:
                            l.append("¬%s(%d)" % (
                                feature_names[k-enc.clause_bank.number_of_features], enc.clause_bank.get_ta_state(j, k)))
                print(" ∧ ".join(l))
                clause_result.append(" ∧ ".join(l))
        """

        similarity = cosine_similarity(profile)

        print("\nWord Similarity\n")
        word_result = ""
        for i in range(len(target_words)):
            print(target_words[i], end=': ')
            sorted_index = np.argsort(-1*similarity[i, :])
            word_result += "\n" + target_words[i] + ": "
            for j in range(1, len(target_words)):
                print("%s(%.2f) " % (
                    target_words[sorted_index[j]], similarity[i, sorted_index[j]]), end=' ')
                word_result += f"{target_words[sorted_index[j]]}: {similarity[i, sorted_index[j]]}, "

            print()

        print("\nTraining Time: %.2f" % (stop_training - start_training))
        if e == epochs - 1:
            temp_data = pd.DataFrame(data=[word_result, f"Precision: {precision}", f"Recall: {recall}", f"Number of examples: {examples_vector[example_index]}", f"Margin: {margin_vector[margin_index]}",
                                     f"Clauses: {clause_vector[clause_index]}", f"Specificity: {specificity_vector[specificity_index]}",
                                           f"Accumulation: {accumulation_vector[accumulation_index]}"])
            temp_data.to_csv('results.csv', index=False,
                             header=False, mode='a')


middle = steps // 2
for i in range(steps):
    if i != middle:
        train(i, middle, middle, middle, middle)
        train(middle, i, middle, middle, middle)
        train(middle, middle, i, middle, middle)
        train(middle, middle, middle, i, middle)
        train(middle, middle, middle, middle, i)
