# Breden Verification Bot

A comprehensive Discord verification system with Whop integration, designed for subscription-based communities requiring member verification through scheduled calls. MADE BY AIDAPTICS

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
- **Admin-Only Commands**: Sensitive operations restricted to administrators
- **Permission Validation**: Verifies bot permissions before operations
- **Error Recovery**: Graceful handling of permission errors

## 🔧 Troubleshooting

### Common Issues
- **Bot Missing Permissions**: Ensure Administrator role is assigned
- **Roles Not Restoring**: Check role hierarchy and bot position
- **Monitoring Not Working**: Verify environment variables are correct
- **Commands Not Appearing**: Run bot restart to sync slash commands

### Debug Tools
- Use `/debug_roles <user>` to check user role status
- Use `/check_stored_roles` to view system state
- Check console logs for detailed debugging information
- Use `/cleanup_tracking` to resolve data inconsistencies

## 📈 Performance

### Optimizations
- **Efficient Role Lookups**: Fast set-based role checking
- **Minimal API Calls**: Optimized Discord API usage
- **Memory Management**: Automatic cleanup of unused data
- **Async Operations**: Non-blocking concurrent processing

### Scalability
- **Large Server Support**: Handles thousands of concurrent users
- **Resource Efficient**: Low memory and CPU usage
- **Rate Limit Handling**: Respects Discord API limits
- **Error Recovery**: Continues operation despite temporary failures

## 🔄 Updates & Maintenance

### Regular Maintenance
- Monitor logs for unusual activity
- Run `/cleanup_tracking` periodically
- Update environment variables as needed
- Restart bot for optimal performance

### Version Updates
- Backup configuration before updates
- Test in development environment first
- Monitor logs after deployment
- Verify all features working correctly

## 📞 Support

For technical support or feature requests, contact the development team. Include relevant logs and error messages for faster resolution.

---

**Built for professional Discord communities requiring robust verification systems.**
