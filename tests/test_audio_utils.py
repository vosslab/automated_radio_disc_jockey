import audio_utils


#============================================
def test_extract_year_value_handles_none() -> None:
	assert audio_utils._extract_year_value(None) is None


#============================================
def test_extract_year_value_reads_embedded_year() -> None:
	assert audio_utils._extract_year_value("Released in 2001 remaster") == "2001"


#============================================
def test_extract_year_value_reads_digit_year() -> None:
	assert audio_utils._extract_year_value("1998") == "1998"
	assert audio_utils._extract_year_value("98") is None


#============================================
def test_extract_year_from_candidates_prefers_first_valid() -> None:
	result = audio_utils._extract_year_from_candidates(None, "nope", "2005", "2012")
	assert result == "2005"

