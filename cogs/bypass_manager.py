import json
import os
import logging
from typing import Set, List, Optional
import discord

class BypassManager:
    def __init__(self):
        self.bypass_file = "bypass_roles.json"
        # Always use absolute path in project root
        self.bypass_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'bypass_roles.json'))
        self.bypass_roles: Set[int] = set()
        self.load_bypass_roles()
    
    def load_bypass_roles(self):
        """Load bypass roles from JSON file"""
        try:
            logging.info(f"[BypassManager] Loading bypass roles from: {self.bypass_file}")
            if os.path.exists(self.bypass_file):
                with open(self.bypass_file, 'r') as f:
                    data = json.load(f)
                    self.bypass_roles = set(data.get('bypass_roles', []))
                    logging.info(f"Loaded {len(self.bypass_roles)} bypass roles from {self.bypass_file}")
            else:
                # Create empty file if it doesn't exist
                self.save_bypass_roles()
                logging.info(f"Created new bypass roles file: {self.bypass_file}")
        except Exception as e:
            logging.error(f"Error loading bypass roles from {self.bypass_file}: {e}")
            self.bypass_roles = set()
    
    def save_bypass_roles(self):
        """Save bypass roles to JSON file"""
        try:
            data = {
                "bypass_roles": list(self.bypass_roles),
                "last_updated": str(discord.utils.utcnow()),
                "description": "Roles that bypass verification requirements"
            }
            with open(self.bypass_file, 'w') as f:
                json.dump(data, f, indent=2)
            logging.info(f"Saved {len(self.bypass_roles)} bypass roles to {self.bypass_file}")
        except Exception as e:
            logging.error(f"Error saving bypass roles to {self.bypass_file}: {e}")
    
    def add_bypass_role(self, role_id: int) -> bool:
        """Add a role to bypass list"""
        if role_id not in self.bypass_roles:
            self.bypass_roles.add(role_id)
            self.save_bypass_roles()
            return True
        return False
    
    def remove_bypass_role(self, role_id: int) -> bool:
        """Remove a role from bypass list"""
        if role_id in self.bypass_roles:
            self.bypass_roles.remove(role_id)
            self.save_bypass_roles()
            return True
        return False
    
    def has_bypass_role(self, member: discord.Member) -> bool:
        """Check if member has any bypass roles"""
        if not self.bypass_roles:
            return False
        
        member_role_ids = {role.id for role in member.roles}
        return bool(member_role_ids & self.bypass_roles)
    
    def get_bypass_roles(self) -> Set[int]:
        """Get all bypass role IDs"""
        return self.bypass_roles.copy()
    
    def get_bypass_role_names(self, guild: discord.Guild) -> List[str]:
        """Get bypass role names for a guild"""
        names = []
        for role_id in self.bypass_roles:
            role = guild.get_role(role_id)
            if role:
                names.append(role.name)
            else:
                names.append(f"Unknown Role (ID: {role_id})")
        return names

# Global instance
bypass_manager = BypassManager()