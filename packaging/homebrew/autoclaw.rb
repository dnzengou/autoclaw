# Homebrew formula — publish to a tap repo (e.g. autoclaw/homebrew-tap).
# Each release CI step should update `version` and the four sha256 lines below.
class Autoclaw < Formula
  desc "Self-improving AI experiment loop for Claude Cowork"
  homepage "https://autoclaw.dev"
  version "0.1.0"
  license "MIT"

  on_macos do
    if Hardware::CPU.arm?
      url "https://github.com/dnzengou/autoclaw/releases/download/v#{version}/autoclaw-aarch64-apple-darwin"
      sha256 "REPLACE_WITH_RELEASE_SHA256_DARWIN_ARM64"
    else
      url "https://github.com/dnzengou/autoclaw/releases/download/v#{version}/autoclaw-x86_64-apple-darwin"
      sha256 "REPLACE_WITH_RELEASE_SHA256_DARWIN_AMD64"
    end
  end

  on_linux do
    if Hardware::CPU.arm?
      url "https://github.com/dnzengou/autoclaw/releases/download/v#{version}/autoclaw-aarch64-unknown-linux-gnu"
      sha256 "REPLACE_WITH_RELEASE_SHA256_LINUX_ARM64"
    else
      url "https://github.com/dnzengou/autoclaw/releases/download/v#{version}/autoclaw-x86_64-unknown-linux-gnu"
      sha256 "REPLACE_WITH_RELEASE_SHA256_LINUX_AMD64"
    end
  end

  def install
    bin.install Dir["*"].first => "autoclaw"
  end

  test do
    assert_match "autoclaw", shell_output("#{bin}/autoclaw --help")
  end
end
