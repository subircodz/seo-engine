"""Unit tests for SERP feature domain models (Phase 6N-A).

Covers:
- SERPFeatureType enum values
- SearchSERPFeature valid creation
- invalid feature_type
- invalid position
- invalid/empty required fields
- URL validation and domain extraction
- metadata validation
- immutability
- deterministic equality
- backward compatibility with SearchResultItem.serp_features
"""

from dataclasses import FrozenInstanceError

import pytest

from sie.domain.models.search_result import SearchResultItem
from sie.domain.models.search_serp import SearchSERPFeature, SERPFeatureType

# ════════════════════════════════════════════════════════════════════════════
# SERPFeatureType enum
# ════════════════════════════════════════════════════════════════════════════


class TestSERPFeatureType:
    @pytest.mark.parametrize(
        "member_name, expected_value",
        [
            ("FEATURED_SNIPPET", "featured_snippet"),
            ("PEOPLE_ALSO_ASK", "people_also_ask"),
            ("KNOWLEDGE_PANEL", "knowledge_panel"),
            ("LOCAL_PACK", "local_pack"),
            ("SHOPPING", "shopping"),
            ("VIDEO", "video"),
            ("IMAGE_PACK", "image_pack"),
            ("NEWS", "news"),
            ("OTHER", "other"),
        ],
    )
    def test_every_supported_enum_value(self, member_name, expected_value):
        member = getattr(SERPFeatureType, member_name)
        assert member.value == expected_value
        assert member == expected_value

    def test_enum_is_string_enum(self):
        assert SERPFeatureType.FEATURED_SNIPPET == "featured_snippet"
        assert isinstance(SERPFeatureType.FEATURED_SNIPPET, str)

    def test_all_expected_members_present(self):
        expected = {
            "featured_snippet",
            "people_also_ask",
            "knowledge_panel",
            "local_pack",
            "shopping",
            "video",
            "image_pack",
            "news",
            "other",
        }
        actual = {member.value for member in SERPFeatureType}
        assert actual == expected


# ════════════════════════════════════════════════════════════════════════════
# SearchSERPFeature — valid creation
# ════════════════════════════════════════════════════════════════════════════


class TestSearchSERPFeatureValid:
    def test_minimal_feature(self):
        feature = SearchSERPFeature(feature_type=SERPFeatureType.FEATURED_SNIPPET)
        assert feature.feature_type is SERPFeatureType.FEATURED_SNIPPET
        assert feature.position is None
        assert feature.title is None
        assert feature.url is None
        assert feature.domain is None
        assert feature.metadata == ()

    def test_feature_with_position(self):
        feature = SearchSERPFeature(
            feature_type=SERPFeatureType.LOCAL_PACK,
            position=4,
        )
        assert feature.position == 4

    def test_feature_with_title(self):
        feature = SearchSERPFeature(
            feature_type=SERPFeatureType.PEOPLE_ALSO_ASK,
            title="People also ask",
        )
        assert feature.title == "People also ask"

    def test_feature_with_url_and_domain(self):
        feature = SearchSERPFeature(
            feature_type=SERPFeatureType.FEATURED_SNIPPET,
            url="https://example.com/guide",
        )
        assert feature.url == "https://example.com/guide"
        assert feature.domain == "example.com"

    def test_feature_url_strips_www(self):
        feature = SearchSERPFeature(
            feature_type=SERPFeatureType.KNOWLEDGE_PANEL,
            url="https://www.example.co.uk/page",
        )
        assert feature.domain == "example.co.uk"

    def test_feature_url_casefolded_domain(self):
        feature = SearchSERPFeature(
            feature_type=SERPFeatureType.VIDEO,
            url="https://EXAMPLE.COM/video",
        )
        assert feature.domain == "example.com"

    def test_feature_url_port_stripped(self):
        feature = SearchSERPFeature(
            feature_type=SERPFeatureType.SHOPPING,
            url="https://example.com:8080/item",
        )
        assert feature.domain == "example.com"

    def test_feature_with_metadata(self):
        feature = SearchSERPFeature(
            feature_type=SERPFeatureType.OTHER,
            _metadata=(("key1", "value1"), ("key2", "value2")),
        )
        assert feature.metadata == (
            ("key1", "value1"),
            ("key2", "value2"),
        )

    def test_feature_full(self):
        feature = SearchSERPFeature(
            feature_type=SERPFeatureType.FEATURED_SNIPPET,
            position=1,
            title="Answer",
            url="https://example.com/answer",
            _metadata=(("source", "google"), ("type", "paragraph")),
        )
        assert feature.feature_type is SERPFeatureType.FEATURED_SNIPPET
        assert feature.position == 1
        assert feature.title == "Answer"
        assert feature.url == "https://example.com/answer"
        assert feature.domain == "example.com"
        assert feature.metadata == (
            ("source", "google"),
            ("type", "paragraph"),
        )


# ════════════════════════════════════════════════════════════════════════════
# SearchSERPFeature — invalid creation
# ════════════════════════════════════════════════════════════════════════════


class TestSearchSERPFeatureInvalid:
    def test_invalid_feature_type_string(self):
        with pytest.raises(ValueError, match="feature_type"):
            SearchSERPFeature(feature_type="not_a_real_feature")  # type: ignore[arg-type]

    def test_position_negative_rejected(self):
        with pytest.raises(ValueError, match="position"):
            SearchSERPFeature(feature_type=SERPFeatureType.LOCAL_PACK, position=-3)

    def test_non_integer_position_rejected(self):
        with pytest.raises(ValueError, match="position"):
            SearchSERPFeature(
                feature_type=SERPFeatureType.LOCAL_PACK,
                position=1.5,  # type: ignore[arg-type]
            )

    def test_boolean_position_rejected(self):
        with pytest.raises(ValueError, match="position"):
            SearchSERPFeature(
                feature_type=SERPFeatureType.LOCAL_PACK,
                position=True,  # type: ignore[arg-type]
            )

    def test_string_position_rejected(self):
        with pytest.raises(ValueError, match="position"):
            SearchSERPFeature(
                feature_type=SERPFeatureType.LOCAL_PACK,
                position="3",  # type: ignore[arg-type]
            )

    def test_invalid_url_rejected(self):
        with pytest.raises(ValueError, match="url"):
            SearchSERPFeature(
                feature_type=SERPFeatureType.FEATURED_SNIPPET,
                url="example.com/page",
            )

    def test_empty_title_rejected(self):
        with pytest.raises(ValueError, match="title"):
            SearchSERPFeature(
                feature_type=SERPFeatureType.PEOPLE_ALSO_ASK,
                title="   ",
            )

    def test_none_title_accepted(self):
        feature = SearchSERPFeature(
            feature_type=SERPFeatureType.PEOPLE_ALSO_ASK,
            title=None,  # type: ignore[arg-type]
        )
        assert feature.title is None

    def test_ftp_url_rejected(self):
        with pytest.raises(ValueError, match="url"):
            SearchSERPFeature(
                feature_type=SERPFeatureType.FEATURED_SNIPPET,
                url="ftp://example.com/page",
            )

    def test_empty_url_rejected(self):
        with pytest.raises(ValueError, match="url"):
            SearchSERPFeature(
                feature_type=SERPFeatureType.FEATURED_SNIPPET,
                url="",
            )

    def test_invalid_metadata_not_tuple(self):
        with pytest.raises(ValueError, match="Metadata"):
            SearchSERPFeature(
                feature_type=SERPFeatureType.OTHER,
                _metadata=[("key", "val")],  # type: ignore[arg-type]
            )

    def test_invalid_metadata_wrong_inner_length(self):
        with pytest.raises(ValueError, match="Metadata"):
            SearchSERPFeature(
                feature_type=SERPFeatureType.OTHER,
                _metadata=(("key", "val", "extra"),),
            )

    def test_invalid_metadata_non_string_values(self):
        with pytest.raises(ValueError, match="Metadata"):
            SearchSERPFeature(
                feature_type=SERPFeatureType.OTHER,
                _metadata=(("key", 123),),  # type: ignore[arg-type]
            )

    def test_empty_metadata_tuple_accepted(self):
        feature = SearchSERPFeature(
            feature_type=SERPFeatureType.OTHER,
            _metadata=(),
        )
        assert feature.metadata == ()


# ════════════════════════════════════════════════════════════════════════════
# SearchSERPFeature — immutability & equality
# ════════════════════════════════════════════════════════════════════════════


class TestSearchSERPFeatureImmutability:
    def test_frozen_feature_type(self):
        feature = SearchSERPFeature(feature_type=SERPFeatureType.FEATURED_SNIPPET)
        with pytest.raises(FrozenInstanceError):
            feature.feature_type = SERPFeatureType.KNOWLEDGE_PANEL  # type: ignore[misc]

    def test_frozen_position(self):
        feature = SearchSERPFeature(feature_type=SERPFeatureType.LOCAL_PACK, position=1)
        with pytest.raises(FrozenInstanceError):
            feature.position = 5  # type: ignore[misc]

    def test_frozen_title(self):
        feature = SearchSERPFeature(feature_type=SERPFeatureType.PEOPLE_ALSO_ASK, title="PAA")
        with pytest.raises(FrozenInstanceError):
            feature.title = "Other"  # type: ignore[misc]

    def test_frozen_url(self):
        feature = SearchSERPFeature(
            feature_type=SERPFeatureType.FEATURED_SNIPPET,
            url="https://example.com",
        )
        with pytest.raises(FrozenInstanceError):
            feature.url = "https://other.com"  # type: ignore[misc]

    def test_frozen_domain(self):
        feature = SearchSERPFeature(
            feature_type=SERPFeatureType.FEATURED_SNIPPET,
            url="https://example.com",
        )
        with pytest.raises(FrozenInstanceError):
            feature.domain = "other.com"  # type: ignore[misc]

    def test_frozen_metadata(self):
        feature = SearchSERPFeature(
            feature_type=SERPFeatureType.OTHER,
            _metadata=(("k", "v"),),
        )
        with pytest.raises(FrozenInstanceError):
            feature._metadata = (("x", "y"),)  # type: ignore[misc]


class TestSearchSERPFeatureEquality:
    def test_equal_features(self):
        f1 = SearchSERPFeature(
            feature_type=SERPFeatureType.FEATURED_SNIPPET,
            position=1,
            title="Answer",
            url="https://example.com",
        )
        f2 = SearchSERPFeature(
            feature_type=SERPFeatureType.FEATURED_SNIPPET,
            position=1,
            title="Answer",
            url="https://example.com",
        )
        assert f1 == f2

    def test_different_feature_type_unequal(self):
        f1 = SearchSERPFeature(feature_type=SERPFeatureType.FEATURED_SNIPPET)
        f2 = SearchSERPFeature(feature_type=SERPFeatureType.KNOWLEDGE_PANEL)
        assert f1 != f2

    def test_different_position_unequal(self):
        f1 = SearchSERPFeature(feature_type=SERPFeatureType.LOCAL_PACK, position=1)
        f2 = SearchSERPFeature(feature_type=SERPFeatureType.LOCAL_PACK, position=2)
        assert f1 != f2

    def test_none_vs_explicit_fields_differ(self):
        f1 = SearchSERPFeature(feature_type=SERPFeatureType.OTHER)
        f2 = SearchSERPFeature(feature_type=SERPFeatureType.OTHER, title="Title")
        assert f1 != f2

    def test_deterministic_equality_same_object(self):
        f = SearchSERPFeature(
            feature_type=SERPFeatureType.IMAGE_PACK,
            position=10,
            _metadata=(("k", "v"),),
        )
        assert f == f

    def test_can_be_used_in_set(self):
        f1 = SearchSERPFeature(feature_type=SERPFeatureType.NEWS)
        f2 = SearchSERPFeature(feature_type=SERPFeatureType.NEWS)
        assert len({f1, f2}) == 1


# ════════════════════════════════════════════════════════════════════════════
# Backward compatibility with SearchResultItem
# ════════════════════════════════════════════════════════════════════════════


class TestSearchResultItemBackwardCompat:
    def test_item_with_no_serp_features(self):
        item = SearchResultItem(position=1, title="Title", url="https://example.com")
        assert item.serp_features == ()

    def test_item_with_serp_features(self):
        feature = SearchSERPFeature(
            feature_type=SERPFeatureType.FEATURED_SNIPPET,
            position=0,
        )
        item = SearchResultItem(
            position=1,
            title="Title",
            url="https://example.com",
            serp_features=(feature,),
        )
        assert len(item.serp_features) == 1
        assert item.serp_features[0].feature_type is SERPFeatureType.FEATURED_SNIPPET

    def test_item_with_empty_tuple(self):
        item = SearchResultItem(
            position=2,
            title="Title",
            url="https://example.com",
            serp_features=(),
        )
        assert item.serp_features == ()

    def test_item_immutable(self):
        item = SearchResultItem(position=1, title="Title", url="https://example.com")
        with pytest.raises(FrozenInstanceError):
            item.serp_features = ()  # type: ignore[misc]

    def test_item_with_multiple_features(self):
        features = (
            SearchSERPFeature(feature_type=SERPFeatureType.KNOWLEDGE_PANEL),
            SearchSERPFeature(feature_type=SERPFeatureType.SHOPPING),
            SearchSERPFeature(feature_type=SERPFeatureType.VIDEO),
        )
        item = SearchResultItem(
            position=1,
            title="Title",
            url="https://example.com",
            serp_features=features,
        )
        assert len(item.serp_features) == 3
        assert {f.feature_type for f in item.serp_features} == {
            SERPFeatureType.KNOWLEDGE_PANEL,
            SERPFeatureType.SHOPPING,
            SERPFeatureType.VIDEO,
        }
