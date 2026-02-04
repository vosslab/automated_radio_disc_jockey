import llm_wrapper


#============================================
def test_extract_xml_tag_prefers_last_match() -> None:
	raw = "<response>One</response> junk <response>Two</response>"
	assert llm_wrapper.extract_xml_tag(raw, "response") == "Two"


#============================================
def test_extract_xml_tag_handles_missing_close() -> None:
	raw = "<response>Hello there"
	assert llm_wrapper.extract_xml_tag(raw, "response") == "Hello there"


#============================================
def test_extract_xml_tag_returns_empty_when_missing() -> None:
	assert llm_wrapper.extract_xml_tag("no tags here", "response") == ""


#============================================
def test_extract_response_text_accepts_trailing_missing_close() -> None:
	raw = "prefix <response>Hello there"
	assert llm_wrapper.extract_response_text(raw) == "Hello there"


#============================================
def test_extract_response_text_returns_empty_when_missing() -> None:
	assert llm_wrapper.extract_response_text("") == ""

