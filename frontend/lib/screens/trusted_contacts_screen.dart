import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_models.dart';
import '../main.dart';
import '../theme.dart';
import '../widgets/common_widgets.dart';

class TrustedContactsScreen extends ConsumerStatefulWidget {
  const TrustedContactsScreen({super.key});

  @override
  ConsumerState<TrustedContactsScreen> createState() =>
      _TrustedContactsScreenState();
}

class _TrustedContactsScreenState extends ConsumerState<TrustedContactsScreen> {
  final Set<int> _busyContactIds = {};
  bool _isTestingAll = false;

  @override
  Widget build(BuildContext context) {
    final contacts = ref.watch(trustedContactsProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Trusted family members')),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(trustedContactsProvider);
          await ref.read(trustedContactsProvider.future);
        },
        child: ListView(
          padding: const EdgeInsets.fromLTRB(22, 12, 22, 36),
          children: [
            const Panel(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Before adding family',
                    style: TextStyle(fontWeight: FontWeight.w800, fontSize: 17),
                  ),
                  SizedBox(height: 10),
                  _Instruction(
                    number: '1',
                    text: 'Share your ScamShield bot with each family member. They must open the bot and press Start or send /start first; Telegram blocks bots from starting private chats.',
                  ),
                  SizedBox(height: 9),
                  _Instruction(
                    number: '2',
                    text: 'Ask them to send you their numeric Telegram Chat ID. They can find it by messaging @userinfobot after starting the ScamShield bot.',
                  ),
                  SizedBox(height: 9),
                  _Instruction(
                    number: '3',
                    text: 'Add their name and Chat ID below, then send a test notification to confirm delivery.',
                  ),
                  SizedBox(height: 11),
                  Text(
                    'Alerts include risk details and safety advice, not the full private conversation.',
                    style: TextStyle(color: ScamColors.muted),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 22),
            SectionHeading(
              title: 'Family recipients',
              subtitle: 'Enabled members receive DANGER-level Telegram alerts.',
              trailing: IconButton.filledTonal(
                tooltip: 'Add family member',
                onPressed: _openAddDialog,
                icon: const Icon(Icons.person_add_alt_1),
              ),
            ),
            const SizedBox(height: 11),
            contacts.when(
              loading: () => const Padding(
                padding: EdgeInsets.all(28),
                child: Center(child: CircularProgressIndicator()),
              ),
              error: (error, _) => ErrorNotice(
                message: error.toString(),
                onRetry: () => ref.invalidate(trustedContactsProvider),
              ),
              data: (items) => items.isEmpty
                  ? const EmptyNotice(
                      title: 'No family members added',
                      message:
                          'Add a trusted person to receive high-risk alerts.',
                      icon: Icons.family_restroom,
                    )
                  : Column(
                      children: [
                        for (final contact in items) ...[
                          _ContactCard(
                            contact: contact,
                            busy: _busyContactIds.contains(contact.id),
                            onEnabledChanged: (enabled) =>
                                _updateContact(contact, enabled: enabled),
                            onEdit: () => _openEditDialog(contact),
                            onDelete: () => _deleteContact(contact),
                            onTest: () => _testContact(contact),
                          ),
                          const SizedBox(height: 10),
                        ],
                      ],
                    ),
            ),
            if (contacts.asData?.value.any((contact) => contact.enabled) ??
                false) ...[
              const SizedBox(height: 8),
              FilledButton.icon(
                onPressed: _isTestingAll ? null : _testAll,
                icon: _isTestingAll
                    ? const SizedBox.square(
                        dimension: 17,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.mark_email_read_outlined),
                label: Text(
                  _isTestingAll
                      ? 'Sending test messages…'
                      : 'Test all enabled family members',
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Future<void> _openAddDialog() async {
    final saved = await showDialog<bool>(
      context: context,
      builder: (_) => const _ContactEditorDialog(),
    );
    if (saved == true && mounted) {
      ref.invalidate(trustedContactsProvider);
      ref.invalidate(notificationStatusProvider);
      _showMessage('Trusted family member added.');
    }
  }

  Future<void> _openEditDialog(TrustedContact contact) async {
    final saved = await showDialog<bool>(
      context: context,
      builder: (_) => _ContactEditorDialog(contact: contact),
    );
    if (saved == true && mounted) {
      ref.invalidate(trustedContactsProvider);
      ref.invalidate(notificationStatusProvider);
      _showMessage('Trusted family member updated.');
    }
  }

  Future<void> _updateContact(
    TrustedContact contact, {
    required bool enabled,
  }) async {
    setState(() => _busyContactIds.add(contact.id));
    try {
      await ref
          .read(apiProvider)
          .updateTrustedContact(
            contactId: contact.id,
            name: contact.name,
            chatId: contact.chatId,
            enabled: enabled,
          );
      ref.invalidate(trustedContactsProvider);
      ref.invalidate(notificationStatusProvider);
    } catch (error) {
      _showMessage(error.toString());
    } finally {
      if (mounted) setState(() => _busyContactIds.remove(contact.id));
    }
  }

  Future<void> _deleteContact(TrustedContact contact) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Remove family member?'),
        content: Text(
          '${contact.name} will no longer receive ScamShield alerts.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Remove'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;

    setState(() => _busyContactIds.add(contact.id));
    try {
      await ref.read(apiProvider).deleteTrustedContact(contact.id);
      ref.invalidate(trustedContactsProvider);
      ref.invalidate(notificationStatusProvider);
      _showMessage('Family member removed.');
    } catch (error) {
      _showMessage(error.toString());
    } finally {
      if (mounted) setState(() => _busyContactIds.remove(contact.id));
    }
  }

  Future<void> _testContact(TrustedContact contact) async {
    setState(() => _busyContactIds.add(contact.id));
    try {
      final result = await ref.read(apiProvider).testTrustedContact(contact.id);
      _showMessage(
        result.success
            ? 'Test notification delivered to ${result.name}.'
            : 'Could not deliver to ${result.name}: ${result.message}',
      );
    } catch (error) {
      _showMessage(error.toString());
    } finally {
      if (mounted) setState(() => _busyContactIds.remove(contact.id));
    }
  }

  Future<void> _testAll() async {
    setState(() => _isTestingAll = true);
    try {
      final result = await ref.read(apiProvider).testEnabledTrustedContacts();
      if (result.total == 0) {
        _showMessage('No enabled family members to test.');
      } else {
        _showMessage(
          'Test notifications: ${result.successCount} delivered, '
          '${result.failureCount} failed. Ask failed recipients to send /start to the bot.',
        );
      }
    } catch (error) {
      _showMessage(error.toString());
    } finally {
      if (mounted) setState(() => _isTestingAll = false);
    }
  }

  void _showMessage(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }
}

class _ContactCard extends StatelessWidget {
  const _ContactCard({
    required this.contact,
    required this.busy,
    required this.onEnabledChanged,
    required this.onEdit,
    required this.onDelete,
    required this.onTest,
  });

  final TrustedContact contact;
  final bool busy;
  final ValueChanged<bool> onEnabledChanged;
  final VoidCallback onEdit;
  final VoidCallback onDelete;
  final VoidCallback onTest;

  @override
  Widget build(BuildContext context) => Panel(
    padding: const EdgeInsets.fromLTRB(16, 11, 12, 13),
    child: Column(
      children: [
        Row(
          children: [
            CircleAvatar(
              backgroundColor: ScamColors.mint.withValues(alpha: .12),
              child: const Icon(Icons.person_outline, color: ScamColors.mint),
            ),
            const SizedBox(width: 11),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    contact.name,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 3),
                  SelectableText(
                    'Chat ID: ${contact.chatId}',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            ),
            if (busy)
              const SizedBox.square(
                dimension: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            else
              Switch(value: contact.enabled, onChanged: onEnabledChanged),
          ],
        ),
        const Divider(height: 22),
        Row(
          children: [
            Text(
              contact.enabled ? 'Alerts enabled' : 'Alerts paused',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: contact.enabled ? ScamColors.safe : ScamColors.muted,
              ),
            ),
            const Spacer(),
            IconButton(
              tooltip: 'Send a test notification',
              onPressed: busy ? null : onTest,
              icon: const Icon(Icons.send_outlined),
            ),
            IconButton(
              tooltip: 'Edit family member',
              onPressed: busy ? null : onEdit,
              icon: const Icon(Icons.edit_outlined),
            ),
            IconButton(
              tooltip: 'Remove family member',
              onPressed: busy ? null : onDelete,
              icon: const Icon(Icons.delete_outline, color: ScamColors.warning),
            ),
          ],
        ),
      ],
    ),
  );
}

class _ContactEditorDialog extends ConsumerStatefulWidget {
  const _ContactEditorDialog({this.contact});

  final TrustedContact? contact;

  @override
  ConsumerState<_ContactEditorDialog> createState() =>
      _ContactEditorDialogState();
}

class _ContactEditorDialogState extends ConsumerState<_ContactEditorDialog> {
  late final TextEditingController _nameController;
  late final TextEditingController _chatIdController;
  final _formKey = GlobalKey<FormState>();
  bool _enabled = true;
  bool _saving = false;
  String? _error;

  bool get _editing => widget.contact != null;

  @override
  void initState() {
    super.initState();
    _nameController = TextEditingController(text: widget.contact?.name ?? '');
    _chatIdController = TextEditingController(
      text: widget.contact?.chatId ?? '',
    );
    _enabled = widget.contact?.enabled ?? true;
  }

  @override
  void dispose() {
    _nameController.dispose();
    _chatIdController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text(_editing ? 'Edit family member' : 'Add family member'),
    content: SizedBox(
      width: 430,
      child: Form(
        key: _formKey,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextFormField(
              controller: _nameController,
              enabled: !_saving,
              maxLength: 80,
              textCapitalization: TextCapitalization.words,
              decoration: const InputDecoration(labelText: 'Name'),
              validator: (value) {
                final name = value?.trim() ?? '';
                if (name.isEmpty) return 'Enter a family member name.';
                if (name.length > 80) {
                  return 'Name must be 80 characters or less.';
                }
                return null;
              },
            ),
            TextFormField(
              controller: _chatIdController,
              enabled: !_saving,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(
                labelText: 'Telegram Chat ID',
                helperText:
                    'Numeric ID, 5–20 digits; group IDs may start with -.',
              ),
              validator: (value) {
                if (!RegExp(r'^-?\d{5,20}$').hasMatch(value?.trim() ?? '')) {
                  return 'Enter a valid numeric Telegram Chat ID.';
                }
                return null;
              },
            ),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Receive DANGER alerts'),
              value: _enabled,
              onChanged: _saving
                  ? null
                  : (value) => setState(() => _enabled = value),
            ),
            if (_error != null)
              Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  _error!,
                  style: const TextStyle(color: ScamColors.danger),
                ),
              ),
          ],
        ),
      ),
    ),
    actions: [
      TextButton(
        onPressed: _saving ? null : () => Navigator.pop(context, false),
        child: const Text('Cancel'),
      ),
      FilledButton(
        onPressed: _saving ? null : _save,
        child: _saving
            ? const SizedBox.square(
                dimension: 17,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            : Text(_editing ? 'Save changes' : 'Add member'),
      ),
    ],
  );

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final api = ref.read(apiProvider);
      if (_editing) {
        await api.updateTrustedContact(
          contactId: widget.contact!.id,
          name: _nameController.text.trim(),
          chatId: _chatIdController.text.trim(),
          enabled: _enabled,
        );
      } else {
        await api.createTrustedContact(
          name: _nameController.text.trim(),
          chatId: _chatIdController.text.trim(),
          enabled: _enabled,
        );
      }
      if (mounted) Navigator.pop(context, true);
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }
}

class _Instruction extends StatelessWidget {
  const _Instruction({required this.number, required this.text});

  final String number;
  final String text;

  @override
  Widget build(BuildContext context) => Row(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Container(
        width: 23,
        height: 23,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: ScamColors.mint.withValues(alpha: .13),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Text(
          number,
          style: const TextStyle(
            color: ScamColors.mint,
            fontSize: 12,
            fontWeight: FontWeight.w800,
          ),
        ),
      ),
      const SizedBox(width: 10),
      Expanded(child: Text(text)),
    ],
  );
}
