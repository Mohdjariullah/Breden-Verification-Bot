# AIdaptics Whop Gatekeeper

A comprehensive Discord verification system with Whop integration, designed for subscription-based communities requiring member verification through scheduled calls. Built by AIdaptics.

## 🚀 Features

### Core Verification System
- **Automated Role Management**: Automatically detects and removes subscription roles from new members
- **Ticket-Based Verification**: Creates private verification channels for each user
- **Calendly Integration**: Seamless booking system for onboarding calls
- **Real-time Role Protection**: Prevents external bots from interfering with the verification process

### Advanced Role Monitoring
- **Whop Bot Protection**: Continuously monitors and prevents Whop bot from re-adding roles to unverified users
- **Race Condition Handling**: Prevents conflicts during role restoration
- **Persistent Data Tracking**: Maintains user role data across bot restarts
- **Automatic Cleanup**: Removes orphaned data for users who leave the server

### Administrative Tools
- **Comprehensive Logging**: Detailed logs of all verification activities
- **Debug Commands**: Advanced troubleshooting tools for administrators
- **Manual Verification**: Force verify users when needed
- **Status Monitoring**: Real-time tracking of pending verifications
- **Strict Admin-Only Controls**: All sensitive commands (including bypass management) are strictly admin-only, protected by Discord permissions and runtime checks

### Ticket System Improvements
- **One Ticket Per User**: Only one verification ticket can exist per user at a time; duplicate ticket creation is prevented
- **Button Cooldown**: The verification button enforces a cooldown to prevent spam or race conditions

## 🛠️ Technical Architecture

### Modular Design
- **Cog-based Structure**: Organized into separate modules for maintainability
- **Async Programming**: Efficient handling of multiple concurrent operations
- **Error Handling**: Robust error management with automatic recovery
- **Scalable Design**: Built to handle large servers with thousands of members

### Database Management
- **In-memory Storage**: Fast access to user verification data
- **Persistent Tracking**: Maintains state across bot restarts
- **Automatic Cleanup**: Removes stale data automatically

## 📋 Commands

### User Commands
- **Verification Button**: Start the verification process through an interactive embed

### Admin Commands (Slash Commands)
- `/setup_verification` - Setup verification system in current channel
- `/setup_logs <channel>` - Configure logging channel
- `/setup_permissions` - Configure channel permissions for verification
- `/refresh_welcome` - Refresh the welcome message
- `/check_stored_roles` - View pending verifications
- `/force_verify <user>` - Manually verify a user
- `/debug_roles <user>` - Debug role information for troubleshooting
- `/cleanup_tracking` - Clean up orphaned tracking data
- `/ping` - Test bot responsiveness

## 🔧 Setup & Configuration

### Environment Variables
```env
TOKEN=your_discord_bot_token
GUILD_ID=your_server_id
WELCOME_CHANNEL_ID=welcome_channel_id
CALENDLY_LINK=your_calendly_booking_link
LAUNCHPAD_ROLE_ID=premium_subscription_role_id
MEMBER_ROLE_ID=free_subscription_role_id
LOGS_CHANNEL_ID=logging_channel_id
```

### Installation
1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Configure environment variables in `.env` file
4. Run the bot: `python main.py`

### Initial Setup
1. Invite bot to server with Administrator permissions
2. Run `/setup_permissions` to configure channel access
3. Run `/setup_verification` in your welcome channel
4. Configure logging with `/setup_logs #logs-channel`

## 🔄 Verification Flow

### For New Members
1. **Join Server**: Member joins with subscription roles from Whop
2. **Role Removal**: Bot automatically removes subscription roles
3. **Monitoring**: User added to monitoring system to prevent role re-addition
4. **Verification**: User clicks verification button to create ticket
5. **Booking**: User books onboarding call via Calendly
6. **Confirmation**: User confirms booking in ticket
7. **Restoration**: Bot restores original subscription roles
8. **Completion**: User gains full server access

### Protection System
- **Continuous Monitoring**: Bot watches for unauthorized role additions
- **Instant Removal**: Automatically removes roles re-added by external systems
- **Verification Tracking**: Maintains verification state until completion
- **Logging**: Records all interference attempts for audit purposes

## 📊 Monitoring & Logging

### Event Logging
- Member joins with subscription roles
- Role removals and restorations
- Verification starts and completions
- External bot interference detection
- Manual admin actions

### Status Tracking
- Users awaiting verification
- Users currently being verified
- Users being monitored for role protection
- System health and performance metrics

## 🛡️ Security Features

### Role Protection
- **Anti-Bypass**: Prevents users from gaining access without verification
- **External Bot Protection**: Blocks interference from Whop and other bots
- **Race Condition Prevention**: Handles concurrent operations safely
- **Data Integrity**: Maintains consistent user state

### Access Control
- **Admin-Only Commands**: Sensitive operations restricted to administrators (bypass commands, force verify, cleanup, etc.)
- **Double Protection**: All admin commands are protected by both Discord permissions and explicit runtime checks
- **Permission Validation**: Verifies bot permissions before operations
- **Error Recovery**: Graceful handling of permission errors

## 🔧 Troubleshooting

### Common Issues
- **Bot Missing Permissions**: Ensure Administrator role is assigned
- **Roles Not Restoring**: Check role hierarchy and bot position
- **Monitoring Not Working**: Verify environment variables are correct
- **Commands Not Appearing**: Run bot restart to sync slash commands
- **Duplicate Tickets**: Only one verification ticket is allowed per user; if you try to create another, you'll be linked to your existing ticket

### Debug Tools
- Use `/debug_roles <user>`