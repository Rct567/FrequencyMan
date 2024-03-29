# FrequencyMan (Anki Plugin)

## Overview

FrequencyMan allows you to intelligently __sort your new cards__ in a personalized way.

Tested on Anki 2.1.60 (Qt6) and 23.12.1 (Qt6).

## Features
- Sort cards based on 'word frequency' and other useful factors.
- Define multiple sorting targets for different decks or selection of cards.
- Customize the ranking factors for each target.
- Define a language for each field.
- Use multiple fields (such as 'front' *and* 'back') to influence the ranking.
- Multiple 'word frequency' lists can be used per language.

## Manual installation

1. Go to the Anki plugin folder, such as `C:\Users\%USERNAME%\AppData\Roaming\Anki2\addons21`
2. Create a new folder for the plugin, such as __addons21\FrequencyMan__
3. Clone the project in the new folder: `git clone https://github.com/Rct567/FrequencyMan.git`
4. Place your word frequency lists (*.txt files) in a subfolder in FrequencyMan/user_files/, such as __\FrequencyMan\user_files\lang_data\en__. If multiple lists exist for a language, they will be combined (based on the highest score/position).
5. Start Anki.

## Download word frequency lists

- Based on Open Subtitles: https://github.com/hermitdave/FrequencyWords/tree/master
- Based on Wikipedia: https://github.com/IlyaSemenov/wikipedia-word-frequency

## Basic usage

1. Open the "FrequencyMan" menu option in the __"Tools" menu__ of the main Anki window.
2. This will open FrequencyMan's main window where you can define your __sorting targets__.
3. Define the targets using a __JSON array of objects__. Each object represents a target to sort (a target can be a deck or a defined selection of cards).
4. Click the __"Reorder Cards" button__ to apply the sorting.

## Configuration examples

### Example 1
Reorders a single deck. This will only match cards with note type `-- My spanish --` located in deck `Spanish`. It will also use the default ranking factors.

The content of your cards and all the ranking metrics will be analyzed per field. The result of this will be combined to determine the final ranking of all new cards. Each field is effectively its own little "universe".

Note: For both languages, a directory should exist (although it could be empty), such as `\user_files\lang_data\en`.

```json
[
    {
        "deck": "Spanish",
        "notes": [
            {
                "fields": {
                    "Meaning": "EN",
                    "Sentence": "ES"
                },
                "name": "-- My spanish --"
            }
        ]
    }
]
```


### Example 2
Reorder the same deck twice, but the first target excludes the sorting of cards whose name matches "Speaking", while the second target only sorts those excluded cards.

The first target only modifies a single ranking factor (giving familiar cards a boost), while the second target reduces the ranking factors used to only 2 factors (with the aim to order by 'as easy as possible').

Note: Both targets use the same 'main scope', which is the selection of cards used to create the data to calculate the ranking. This scope is reduced for each target by `reorder_scope_query` to limit which cards get repositioned.

```json
[
    {
        "deck": "Spanish",
        "notes": [
            {
                "fields": {
                    "Meaning": "EN",
                    "Sentence": "ES"
                },
                "name": "-- My spanish --"
            }
        ],
        "reorder_scope_query": "-card:*Speaking*",
        "ranking_familiarity": 2
    },
    {
        "deck": "Spanish",
        "notes": [
            {
                "fields": {
                    "Meaning": "EN",
                    "Sentence": "ES"
                },
                "name": "-- My spanish --"
            }
        ],
        "reorder_scope_query": "card:*Speaking*",
        "ranking_factors": {
            "familiarity": 1,
            "word_frequency": 1
        }
    }
]
```

### Example #3
Reorder only based on word frequency (using word frequency from both front and back):

```json
[
    {
        "deck": "Spanish::Essential Spanish Vocabulary Top 5000",
        "notes": [
            {
                "name": "Basic-f4e28",
                "fields": {
                    "Spanish": "ES",
                    "English": "EN"
                }
            }
        ],
        "ranking_factors": {
            "word_frequency": 1
        }
    }
]
```

## Tokenizers

Custom tokenizers can be defined in `user_files\tokenizers`.

To use, or to see how a custom tokenizer is defined, you can download [here](https://github.com/Rct567/FrequencyMan_tokenizer_jieba) a working copy of Jieba (ZH), and [here](https://github.com/Rct567/FrequencyMan_tokenizer_janome) a version of Janome (JA).

### Automatic support

FrequencyMan will use tokenizers from other plugins, if there is no custom tokenizer for a given language:

- If [AJT Japanese](https://ankiweb.net/shared/info/1344485230) is installed, Mecab can be used.
- If [Morphman](https://ankiweb.net/shared/info/900801631) is installed, Mecab and Jieba can be used (assuming those also work in Morphman itself).

## Ranking factors

### Default ranking factors

```json
"ranking_factors" : {
    "word_frequency": 1.0,
    "familiarity": 1.0,
    "familiarity_sweetspot": 0.8,
    "lexical_underexposure": 0.4,
    "ideal_focus_word_count": 1.5,
    "ideal_word_count": 1.0,
    "most_obscure_word": 1.0,
    "lowest_fr_least_familiar_word": 1.0,
    "ideal_unseen_word_count": 0.0,
    "word_frequency_lowest": 0.0
}
```

### Description

- `word_frequency`: Represents the _word frequency_ of the words in the content, with a bias toward the lowest value. The _word frequency_ values come from the provided _word frequency lists_.
- `familiarity`: Represents how familiar you are with the words in the content. Like _word_frequency_, it has a bias toward the lowest value. How familiar you are with a word depends on how many times you have seen the word and in what context that specific word was present (the interval and ease of the card, the amount of words in the content etc).
- `familiarity_sweetspot`: Promotes cards with words close to a specific 'sweetspot' of familiarity. This can be used to promote cards with words that have already been introduced to you by reviewed cards, but might benefit from 'reinforcement'. These can be new words, or words that are 'hidden' (non-prominent) in older cards. The 'sweetspot' is 0.45 of the _median familiarity_ score by default. Use target setting `familiarity_sweetspot_point` to customize this value.
- `lexical_underexposure`: Promotes cards with high-frequency words that you are not yet proportionally familiar with. Basically, _lexical_underexposure = (word_frequency-word_familiarity)_. Increasing this value means you will be 'pushed' forward more in your language learning journey (and the word frequency list). Increase the value slightly if you experience too much overlap and not enough new words.
- `ideal_focus_word_count`: Promotes cards with only a single '_focus word_'. See also _N+1_: https://en.wikipedia.org/wiki/Input_hypothesis#Input_hypothesis. A _focus word_ is a word you are not yet appropriately familiar with. By default this is assumed when a word has a familiarity below 0.9 of the median value. Use target setting `focus_words_endpoint` to customize this value.

- `ideal_word_count`: Represents how close the _word count_ of the content is to the defined ideal range. By default this is 2 to 5, but you can customize it per target with:

  ```json
  "ideal_word_count": [1, 8]
  ```
- `most_obscure_word`: Represents the lowest value that can be found when combining both _word_frequency_ and _word_familiarity_.
- `lowest_fr_least_familiar_word`: Represents the lowest word frequency among the least familiar words.
- `ideal_unseen_word_count`: Like _ideal_focus_word_count_, but promotes cards with only a single 'new word' (a word not found in any reviewed card).

## Custom fields

The following fields will be automatically populated when you reorder your cards:

- `fm_focus_words`: A list of focus words for each field. (recommended!)
- `fm_unseen_words`: A list of unseen words (words not found in reviewed cards) for each field.
- `fm_seen_words`: A list of seen words (words found in reviewed cards) for each field.

Dynamic field names (the number at the end can be replaced with the index number of any field defined in the target):

- `fm_main_focus_word_0`: The focus word with the lowest familiarity for field 0.
- `fm_main_focus_word_static_0`: The focus word with the lowest familiarity for field 0. This field will not be updated once set.
- `fm_lowest_fr_word_0`: The word with the lowest word frequency for field 0.
- `fm_lowest_familiarity_word_0`: The word with the lowest familiarity for field 0.
- `fm_lowest_familiarity_word_static_0`: The word with the lowest familiarity for field 0. This field will not be updated once set.

For debug purposes:

- `fm_debug_info`: Different metrics and data points for each field.
- `fm_debug_ranking_info`: The resulting score per ranking factor for the note.
- `fm_debug_words_info` The score's for each word for 'word frequency', 'lexical underexposure' and 'familiarity sweetspot'.

### Display focus words on the back of your cards (html example)

```html
{{#fm_focus_words}}
  <p> <span style="opacity:0.65;">Focus:</span> {{fm_focus_words}} </p>
{{/fm_focus_words}}
```

# Target settings

For each defined target, the following setting are available:

| Setting | Type | Description | Default value      |
|---------|------|-------------|-------|
| `deck`    | string | Name of a single deck. | -      |
| `decks`   | string | Names of decks separated by a comma.  | -      |
| `scope_query`   | string | Search query.  | -      |
| `notes`   | array of objects |  | -      |
| `reorder_scope_query`   | string |  | defined by main scope       |
| `ranking_factors`   | object |  | see '[Ranking factors](#default-ranking-factors)'      |
| `familiarity_sweetspot_point`   | float |  |   `0.45`  |
| `suspended_card_value`   | float |  |   `0.5`  |
| `ideal_word_count`   | array with two int's |  |  `[2, 5]`   |
| `focus_words_endpoint`   | float |  |  `0.9`   |
