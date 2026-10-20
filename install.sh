#!/bin/bash
# Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
# Install linkedin-cli

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$HOME/.local/bin"

echo "Installing linkedin-cli..."

# Create install directory
mkdir -p "$INSTALL_DIR"

# Create wrapper script
cat > "$INSTALL_DIR/linkedin-cli" << 'EOF'
#!/bin/bash
exec python3 "$HOME/Projects/other/linkedin-cli/linkedin_cli.py" "$@"
EOF

chmod +x "$INSTALL_DIR/linkedin-cli"

# Create config directory
mkdir -p "$HOME/.config/linkedin-cli"

echo "✅ linkedin-cli installed to $INSTALL_DIR/linkedin-cli"
echo ""
echo "Make sure ~/.local/bin is in your PATH:"
echo '  export PATH="$HOME/.local/bin:$PATH"'
echo ""
echo "Quick start:"
echo "  linkedin-cli --help        # Show help"
echo "  linkedin-cli status        # Check status"
echo "  linkedin-cli queue         # View message queue"
echo "  linkedin-cli queue --process  # Process approved messages"
