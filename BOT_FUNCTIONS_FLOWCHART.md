# 🤖 AIdaptics Whop Gatekeeper Bot - Complete Functions Flowchart

## 📋 Overview
This Discord bot manages subscription verification, member onboarding, and server access control with comprehensive admin tools and analytics.

---

## 🔄 Core Workflows

### 1. **Member Join Process**
```
User Joins Server
        ↓
Check for Bypass Roles
        ↓
┌─────────────────┐
│ Has Bypass Role?│
└─────────────────┘
        ↓
    ┌─ YES ──┐    ┌─ NO ──┐
    ↓         ↓    ↓        ↓
Log Bypass   Exit  Check Subscription Roles
    ↓               ↓
    ┌─────────────────┐
    │ Has Sub Roles?  │
    └─────────────────┘
            ↓
    ┌─ YES ──┐    ┌─ NO ──┐
    ↓         ↓    ↓        ↓
Store Roles  Remove Roles  Add to Member Queue
    ↓               ↓               ↓
Add to Monitoring  Add to Monitoring  Add to Monitoring
    ↓               ↓               ↓
Log Event         Log Event         Log Event
```

### 2. **Verification Process**
```
User Clicks "Start Verification"
        ↓
Check if Already Verified
        ↓
┌─────────────────┐
│ Has Sub Roles?  │
└─────────────────┘
        ↓
    ┌─ YES ──┐    ┌─ NO ──┐
    ↓         ↓    ↓        ↓
Show "Already Verified"  Check Stored Roles
    ↓               ↓
    ┌─────────────────┐
    │ Has Stored Roles?│
    └─────────────────┘
            ↓
    ┌─ YES ──┐    ┌─ NO ──┐
    ↓         ↓    ↓        ↓
Create Ticket  Show "No Subscription"
    ↓
Send Welcome Embed
    ↓
Wait for "I Have Booked"
    ↓
Restore Subscription Roles
    ↓
Monitor Post-Verification
    ↓
Close Ticket
```

### 3. **Role Management System**
```
Role Change Detected
        ↓
Check if User is Monitored
        ↓
┌─────────────────┐
│ Is Monitored?   │
└─────────────────┘
        ↓
    ┌─ YES ──┐    ┌─ NO ──┐
    ↓         ↓    ↓        ↓
Check Source  Ignore  Log Role Change
    ↓
┌─────────────────┐
│ Our Bot Made It?│
└─────────────────┘
        ↓
    ┌─ YES ──┐    ┌─ NO ──┐
    ↓         ↓    ↓        ↓
Ignore       Remove Roles Again
    ↓               ↓
    Log Interference
```

---

## 🛠️ Admin Commands & Functions

### **Core Bot Commands**
- `/ping` - Test bot responsiveness
- `/debug` - Show bot status, cogs, and environment variables

### **Member Management Commands**
- `/test_member_join <user>` - Test member join functionality
- `/check_stored_roles` - Interactive view of pending verifications
- `/force_verify <user>` - Manually verify user and restore roles
- `/debug_roles <user>` - Show detailed role information for user
- `/cleanup_tracking` - Remove orphaned tracking data
- `/scan_existing_members` - Scan all members for proper tracking
- `/funnel_analytics` - Show verification funnel statistics

### **Bypass Role Management**
- `/add_bypass_role <role>` - Add role to verification bypass list
- `/remove_bypass_role <role>` - Remove role from bypass list
- `/list_bypass_roles` - List all bypass roles

### **Verification System Commands**
- `/setup_logs <channel>` - Set verification logs channel
- `/set_booking_link <url>` - Set Calendly booking link
- `/reload_cogs` - Reload all bot cogs
- `/verification_stats` - Show verification statistics

### **Welcome System Commands**
- `/setup_permissions` - ⚠️ DANGEROUS: Hide all channels except welcome
- `/restore_permissions <backup_id>` - Restore channel permissions
- `/refresh_welcome` - Manually refresh welcome message

### **Help & Documentation**
- `/help_admin` - List all admin commands with descriptions

---

## 🔧 System Components

### **Cogs (Modules)**
1. **Verification Cog** - Handles ticket creation and verification flow
2. **Member Management Cog** - Manages role tracking and member monitoring
3. **Welcome Cog** - Manages welcome channel and permissions
4. **Security Utils** - Provides security decorators and logging

### **Key Features**
- **Bypass System**: Roles that skip verification entirely
- **Role Monitoring**: Prevents other bots from re-adding roles
- **Ticket Management**: Creates private verification channels
- **Analytics**: Tracks verification funnel metrics
- **Auto-cleanup**: Removes expired tickets and orphaned data
- **Comprehensive Logging**: All actions logged to designated channel

---

## 📊 Data Management

### **State Persistence**
- `verification_state.json` - Stores ongoing verifications and analytics
- `bypass_roles.json` - Stores bypass role configuration
- `bot.log` - Application logs

### **Environment Variables Required**
- `TOKEN` - Bot token
- `GUILD_ID` - Target server ID
- `WELCOME_CHANNEL_ID` - Welcome channel ID
- `LAUNCHPAD_ROLE_ID` - VIP subscription role ID
- `MEMBER_ROLE_ID` - Free member role ID
- `LOGS_CHANNEL_ID` - Logs channel ID
- `CALENDLY_LINK` - Booking link for verification

---

## 🎯 Bot Capabilities Summary

### **For Users:**
- ✅ Start verification process
- ✅ Book onboarding calls
- ✅ Complete verification to gain access
- ✅ Receive automatic role restoration

### **For Admins:**
- ✅ Monitor all verification activities
- ✅ Manually verify users
- ✅ Manage bypass roles
- ✅ View analytics and statistics
- ✅ Clean up orphaned data
- ✅ Set up channel permissions
- ✅ Debug role issues
- ✅ Reload bot components

### **For Server:**
- ✅ Automatic member onboarding
- ✅ Subscription role management
- ✅ Verification workflow automation
- ✅ Comprehensive activity logging
- ✅ Role interference prevention
- ✅ Analytics and reporting

---

## 🔄 Continuous Processes

### **Background Tasks**
- **Periodic Monitoring**: Checks open tickets every 30 minutes
- **Post-Verification Monitoring**: Monitors users for 2 minutes after verification
- **Auto-Cleanup**: Removes expired tickets after 24 hours
- **State Persistence**: Saves verification state automatically

### **Event Listeners**
- **Member Join**: Automatic role detection and storage
- **Member Leave**: Cleanup tracking data and delete tickets
- **Role Updates**: Prevent external bot interference
- **Command Errors**: Comprehensive error handling and logging

---

## 🛡️ Security Features

- **Admin-only Commands**: All management commands require admin permissions
- **DM Prevention**: All commands blocked in DMs
- **Input Validation**: All user inputs validated and sanitized
- **Error Handling**: Comprehensive error catching and logging
- **Audit Logging**: All admin actions logged with details
- **Rate Limiting**: Cooldown protection on verification buttons

---

*This bot provides a complete Discord server verification and onboarding solution with comprehensive admin tools and analytics.* 