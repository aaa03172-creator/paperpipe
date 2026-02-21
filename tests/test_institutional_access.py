from src.institutional_access import generate_institutional_proxy_url


def test_proxy_url_generation_from_doi():
    url = generate_institutional_proxy_url(doi="10.1000/xyz123")
    assert url == "https://libproxy.knu.ac.kr/_Lib_Proxy_Url/https://doi.org/10.1000/xyz123"
