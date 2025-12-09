class Redgit < Formula
  include Language::Python::Virtualenv

  desc "AI-powered Git workflow assistant with task management integration"
  homepage "https://github.com/ertiz82/redgit"
  url "https://files.pythonhosted.org/packages/source/r/redgit/redgit-0.3.19.tar.gz"
  sha256 "0ad3771f88416dd173334cdc92734d04c2bf06f35e0b22e226dc02d57a56ee8b"
  license "MIT"

  depends_on "python@3.11"

  resource "typer" do
    url "https://files.pythonhosted.org/packages/source/t/typer/typer-0.12.5.tar.gz"
    sha256 "f592f089bedcc8ec1b974125d64851029c3b1af145f04aca64d69410f0c9b722"
  end

  resource "rich" do
    url "https://files.pythonhosted.org/packages/source/r/rich/rich-13.9.4.tar.gz"
    sha256 "439594978a49a09530cff7ebc4b5c7103ef57baf48d5ea3184f21d9a2befa098"
  end

  resource "PyYAML" do
    url "https://files.pythonhosted.org/packages/source/p/pyyaml/pyyaml-6.0.2.tar.gz"
    sha256 "d584d9ec91ad65861cc08d42e834324ef890a082e591037abe114850ff7bbc3e"
  end

  resource "GitPython" do
    url "https://files.pythonhosted.org/packages/source/g/gitpython/GitPython-3.1.43.tar.gz"
    sha256 "35f314a9f878467f5453cc1fee295c3e18e52f1b99f10f6cf5b1682e968a9e7c"
  end

  resource "requests" do
    url "https://files.pythonhosted.org/packages/source/r/requests/requests-2.32.3.tar.gz"
    sha256 "55365417734eb18255590a9ff9eb97e9e1da868d4ccd6402399eaf68af20a760"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    system "#{bin}/rg", "--version"
  end
end