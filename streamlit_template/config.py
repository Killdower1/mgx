import json
import os

class Config:
    def __init__(self):
        self.config_path = "config/"
        self.config_file = "config.json"
        
        if not os.path.exists(self.config_path):
            os.makedirs(self.config_path)
        
        self.config = self.load_config()
    
    def load_config(self):
        """Load configuration from file"""
        try:
            with open(f"{self.config_path}{self.config_file}", 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            # Create default config
            default_config = {
                "thresholds": {
                    "keeper_minimum": 15000000,  # 15M IDR
                    "optimasi_minimum": 8000000   # 8M IDR
                },
                "app_settings": {
                    "currency": "IDR",
                    "date_format": "%Y-%m-%d",
                    "default_period": "2024-03"
                }
            }
            self.save_config_to_file(default_config)
            return default_config
    
    def save_config(self):
        """Save current config to file"""
        try:
            self.save_config_to_file(self.config)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def save_config_to_file(self, config):
        """Save config to file"""
        with open(f"{self.config_path}{self.config_file}", 'w') as f:
            json.dump(config, f, indent=2)
    
    def get_threshold(self, threshold_type):
        """Get threshold value"""
        return self.config.get("thresholds", {}).get(threshold_type, 0)
    
    def set_threshold(self, threshold_type, value):
        """Set threshold value"""
        if "thresholds" not in self.config:
            self.config["thresholds"] = {}
        self.config["thresholds"][threshold_type] = value
    
    def format_currency(self, amount):
        """Format currency based on config"""
        currency = self.config.get("app_settings", {}).get("currency", "IDR")
        if currency == "IDR":
            return f"Rp {amount:,.0f}"
        else:
            return f"{currency} {amount:,.2f}"