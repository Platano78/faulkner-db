#!/bin/bash
# Setup Script for Bi-Weekly Claude Plan Ingestion
# Provides options for systemd timer or cron
# All paths are auto-detected - no configuration needed

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "Claude Plan Ingestion Scheduler Setup"
echo "=========================================="
echo ""
echo "Detected paths:"
echo "  Project: $PROJECT_DIR"
echo "  Scripts: $SCRIPT_DIR"
echo "  User:    $USER"
echo "  Home:    $HOME"
echo ""

# Make the main script executable
chmod +x "$SCRIPT_DIR/scheduled_plan_ingestion.sh"

echo "Choose scheduling method:"
echo "  1) systemd timer (recommended for systemd-based systems)"
echo "  2) cron job (traditional, works everywhere)"
echo "  3) Show both options without installing"
echo ""
read -p "Enter choice [1-3]: " choice

case $choice in
    1)
        echo ""
        echo "Setting up systemd timer..."

        # Create user systemd directory
        mkdir -p ~/.config/systemd/user

        # Generate service file with correct paths
        cat > ~/.config/systemd/user/plan-ingestion.service << EOF
[Unit]
Description=Claude Plan Ingestion Service
Documentation=https://github.com/Platano78/faulkner-db
After=network.target

[Service]
Type=oneshot
WorkingDirectory=$PROJECT_DIR
ExecStart=$SCRIPT_DIR/scheduled_plan_ingestion.sh
StandardOutput=journal
StandardError=journal

# Resource limits
MemoryMax=2G
CPUQuota=50%

[Install]
WantedBy=multi-user.target
EOF

        # Copy timer file
        cp "$SCRIPT_DIR/plan-ingestion.timer" ~/.config/systemd/user/

        # Reload systemd and enable timer
        systemctl --user daemon-reload
        systemctl --user enable plan-ingestion.timer
        systemctl --user start plan-ingestion.timer

        echo ""
        echo "Systemd timer installed and started!"
        echo ""
        echo "Useful commands:"
        echo "  Check status:  systemctl --user status plan-ingestion.timer"
        echo "  View logs:     journalctl --user -u plan-ingestion.service"
        echo "  Run manually:  systemctl --user start plan-ingestion.service"
        echo "  Disable:       systemctl --user disable plan-ingestion.timer"
        ;;

    2)
        echo ""
        echo "Setting up cron job..."

        # Create cron entry for bi-weekly (1st and 15th of each month)
        CRON_ENTRY="0 3 1,15 * * $SCRIPT_DIR/scheduled_plan_ingestion.sh >> $PROJECT_DIR/logs/cron_plan_ingestion.log 2>&1"

        # Check if entry already exists
        if crontab -l 2>/dev/null | grep -q "scheduled_plan_ingestion.sh"; then
            echo "Cron entry already exists. Skipping."
        else
            # Add to crontab
            (crontab -l 2>/dev/null || true; echo "$CRON_ENTRY") | crontab -
            echo "Cron job added!"
        fi

        echo ""
        echo "Cron entry:"
        echo "  $CRON_ENTRY"
        echo ""
        echo "Useful commands:"
        echo "  View crontab:  crontab -l"
        echo "  Edit crontab:  crontab -e"
        echo "  Run manually:  $SCRIPT_DIR/scheduled_plan_ingestion.sh"
        echo "  View logs:     tail -f $PROJECT_DIR/logs/cron_plan_ingestion.log"
        ;;

    3)
        echo ""
        echo "=========================================="
        echo "OPTION 1: Systemd Timer"
        echo "=========================================="
        echo ""
        echo "Run this script with option 1 to auto-generate service files"
        echo "Or manually create ~/.config/systemd/user/plan-ingestion.service"
        echo ""
        echo "Then run:"
        echo "  systemctl --user daemon-reload"
        echo "  systemctl --user enable --now plan-ingestion.timer"
        echo ""
        echo "=========================================="
        echo "OPTION 2: Cron Job"
        echo "=========================================="
        echo ""
        echo "Add this to your crontab (crontab -e):"
        echo ""
        echo "# Bi-weekly Claude plan ingestion (1st and 15th of month at 3 AM)"
        echo "0 3 1,15 * * $SCRIPT_DIR/scheduled_plan_ingestion.sh >> $PROJECT_DIR/logs/cron_plan_ingestion.log 2>&1"
        echo ""
        ;;

    *)
        echo "Invalid choice. Exiting."
        exit 1
        ;;
esac

echo ""
echo "=========================================="
echo "Setup complete!"
echo "=========================================="
echo ""
echo "To run ingestion manually at any time:"
echo "  $SCRIPT_DIR/scheduled_plan_ingestion.sh"
echo ""
