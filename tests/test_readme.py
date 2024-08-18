
from frequencyman.card_ranker import CardRanker
from frequencyman.configured_target import ValidConfiguredTarget


README_FILE_PATH = 'README.md'


class TestReadme:

    def test_readme_content(self):

        readme_content = open(README_FILE_PATH).read()

        # check ranking factors and default weights

        for ranking_factor, default_weight in CardRanker.get_default_ranking_factors_span().items():
            assert '"{}": {}'.format(ranking_factor, default_weight) in readme_content

        # check target properties

        for target_property in ValidConfiguredTarget.get_valid_keys():
            if target_property.startswith('ranking_'):
                continue
            assert "`"+target_property+"`" in readme_content
