from components.geospatial_tracking.data_processing.species import normalize_species, species_matches


def test_normalizes_csv_and_wahis_cattle_variants_the_same():
    assert normalize_species("Domestic - Cattle") == normalize_species("cattle (domestic)")


def test_species_matches_true_for_equivalent_variants():
    assert species_matches("Domestic - Cattle", "cattle (domestic)") is True


def test_species_matches_false_for_different_species():
    assert species_matches("Domestic - Cattle", "buffalo (domestic)") is False


def test_species_matches_false_when_either_side_missing():
    # Absence of evidence is not evidence of agreement.
    assert species_matches(None, "cattle (domestic)") is False
    assert species_matches("Domestic - Cattle", None) is False
    assert species_matches(None, None) is False


def test_normalize_species_none_and_empty():
    assert normalize_species(None) is None
    assert normalize_species("   ") is None
    assert normalize_species("domestic") is None  # filler-only input normalizes to nothing
