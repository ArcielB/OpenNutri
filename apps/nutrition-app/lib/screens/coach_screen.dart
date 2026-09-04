import 'dart:async';

import 'package:flutter/material.dart';

import '../models/personalization.dart';
import '../services/coach_service.dart';
import '../services/voice_recorder.dart';
import '../state/app_controller.dart';
import 'diets_screen.dart';
import 'voice_log_screen.dart';

class CoachScreen extends StatefulWidget {
  const CoachScreen({
    super.key,
    required this.controller,
    required this.coachService,
    required this.refreshDaily,
    required this.dailyLoading,
  });

  final AppController controller;
  final CoachService coachService;
  final Future<void> Function({bool force}) refreshDaily;
  final bool dailyLoading;

  @override
  State<CoachScreen> createState() => _CoachScreenState();
}

class _CoachScreenState extends State<CoachScreen> {
  final _message = TextEditingController();
  final List<_ChatMessage> _messages = const [
    _ChatMessage(
      fromCoach: true,
      text:
          'Tell me what matters: foods you avoid, your schedule, budget, training, preferences, or a goal. I’ll remember only explicit facts and use them in future suggestions.',
    ),
  ].toList();
  bool _sending = false;
  late final VoiceRecorderSession _recorder;
  bool _recording = false;
  String? _processingPath;

  @override
  void initState() {
    super.initState();
    _recorder = OpenNutriVoiceRecorder()..addListener(_onRecorderChanged);
  }

  @override
  void dispose() {
    _recorder.removeListener(_onRecorderChanged);
    unawaited(_recorder.deleteTemporaryFile());
    _recorder.dispose();
    _message.dispose();
    super.dispose();
  }

  void _onRecorderChanged() {
    if (_recording &&
        _recorder.state == VoiceRecorderState.stopped &&
        _recorder.currentPath != null) {
      _recording = false;
      unawaited(_processVoice(_recorder.currentPath!));
    } else if (mounted) {
      setState(() {});
    }
  }

  Future<bool> _ensureEnabled() async {
    if (widget.controller.profile.coachEnabled) return true;
    final accepted = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        icon: const Icon(Icons.auto_awesome),
        title: const Text('Activate your AI coach?'),
        content: const Text(
          'Your chosen goal, saved coach facts, and a compact summary of today’s diary are sent transiently to Google Gemini when advice is generated. If you use the microphone, that temporary recording is also sent for one response and then deleted. OpenNutri keeps your profile on this phone; the resolver does not store coach requests, responses, or audio.\n\nThis is general food guidance, not medical care.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Not now'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Activate coach'),
          ),
        ],
      ),
    );
    if (accepted != true) return false;
    await widget.controller.enableCoach();
    await widget.refreshDaily(force: true);
    return true;
  }

  Future<void> _send() async {
    final text = _message.text.trim();
    if (text.isEmpty || _sending || !await _ensureEnabled()) return;
    setState(() {
      _messages.add(_ChatMessage(fromCoach: false, text: text));
      _message.clear();
      _sending = true;
    });
    try {
      final reply = await widget.coachService.respond(
        controller: widget.controller,
        mode: CoachMode.chat,
        message: text,
      );
      await widget.controller.addCoachMemories(reply.memoryUpdates);
      if (!mounted) return;
      setState(() {
        _messages.add(
          _ChatMessage(
            fromCoach: true,
            text: reply.message,
            remembered: reply.memoryUpdates,
          ),
        );
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _messages.add(
          const _ChatMessage(
            fromCoach: true,
            text:
                'I couldn’t reach the coach service. Nothing from that message was saved—please try again.',
          ),
        );
      });
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  Future<void> _toggleVoice() async {
    if (_sending) return;
    if (_recording) {
      final path = await _recorder.stop();
      if (path != null) await _processVoice(path);
      return;
    }
    if (!await _ensureEnabled() || !mounted) return;
    final started = await _recorder.start();
    if (!mounted) return;
    if (!started) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            _recorder.errorMessage ?? 'Could not start the microphone.',
          ),
        ),
      );
      return;
    }
    setState(() => _recording = true);
  }

  Future<void> _processVoice(String path) async {
    if (_processingPath == path || _sending) return;
    _processingPath = path;
    setState(() {
      _recording = false;
      _sending = true;
    });
    try {
      final reply = await widget.coachService.respondVoice(
        controller: widget.controller,
        wavPath: path,
        languageHint: voiceLanguageHintForLocale(
          WidgetsBinding.instance.platformDispatcher.locale,
        ),
      );
      await widget.controller.addCoachMemories(reply.memoryUpdates);
      if (!mounted) return;
      setState(() {
        _messages.add(
          _ChatMessage(
            fromCoach: false,
            text: reply.transcript ?? 'Voice message',
          ),
        );
        _messages.add(
          _ChatMessage(
            fromCoach: true,
            text: reply.message,
            remembered: reply.memoryUpdates,
          ),
        );
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _messages.add(
          const _ChatMessage(
            fromCoach: true,
            text:
                'I couldn’t finish that voice message. The recording was deleted and nothing was remembered.',
          ),
        );
      });
    } finally {
      await _recorder.deleteTemporaryFile(path);
      _processingPath = null;
      if (mounted) setState(() => _sending = false);
    }
  }

  Future<void> _chooseGoal(NutritionGoal goal) async {
    await widget.controller.updateGoal(goal);
    await widget.refreshDaily(force: true);
  }

  @override
  Widget build(BuildContext context) {
    final profile = widget.controller.profile;
    final brief = widget.controller.dailyCoachBrief;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Coach'),
        actions: [
          IconButton(
            tooltip: 'Refresh today’s advice',
            onPressed: profile.coachEnabled && !widget.dailyLoading
                ? () => widget.refreshDaily(force: true)
                : null,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 30),
        children: [
          _DailyBrief(
            enabled: profile.coachEnabled,
            brief: brief,
            loading: widget.dailyLoading,
            onActivate: _ensureEnabled,
          ),
          const SizedBox(height: 18),
          Text(
            'What are we optimizing for?',
            style: Theme.of(
              context,
            ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final goal in NutritionGoal.values)
                ChoiceChip(
                  selected: profile.goal == goal,
                  label: Text(goal.label),
                  onSelected: (_) => _chooseGoal(goal),
                ),
            ],
          ),
          const SizedBox(height: 22),
          Card(
            clipBehavior: Clip.antiAlias,
            child: ListTile(
              onTap: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (context) =>
                      DietsScreen(controller: widget.controller),
                ),
              ),
              leading: const CircleAvatar(child: Icon(Icons.restaurant_menu)),
              title: Text('Plan: ${profile.diet.name}'),
              subtitle: Text(
                profile.dietNotes.isEmpty
                    ? profile.diet.tagline
                    : profile.dietNotes,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
              trailing: const Icon(Icons.chevron_right),
            ),
          ),
          const SizedBox(height: 20),
          Row(
            children: [
              Expanded(
                child: Text(
                  'Talk to your coach',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
              Text(
                'Remembers explicit facts',
                style: Theme.of(context).textTheme.labelSmall,
              ),
            ],
          ),
          const SizedBox(height: 8),
          Container(
            constraints: const BoxConstraints(maxHeight: 360),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surfaceContainerLow,
              borderRadius: BorderRadius.circular(20),
            ),
            child: ListView.builder(
              shrinkWrap: true,
              padding: const EdgeInsets.all(12),
              itemCount: _messages.length,
              itemBuilder: (context, index) =>
                  _ChatBubble(message: _messages[index]),
            ),
          ),
          const SizedBox(height: 10),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Expanded(
                child: TextField(
                  controller: _message,
                  minLines: 1,
                  maxLines: 4,
                  textInputAction: TextInputAction.send,
                  onSubmitted: (_) => _send(),
                  decoration: const InputDecoration(
                    hintText: 'I train at night and I don’t eat fish…',
                    labelText: 'Tell me something useful',
                  ),
                ),
              ),
              const SizedBox(width: 8),
              IconButton.filledTonal(
                tooltip: _recording ? 'Finish voice message' : 'Speak to coach',
                onPressed: _sending ? null : _toggleVoice,
                icon: Icon(_recording ? Icons.stop_rounded : Icons.mic_rounded),
              ),
              const SizedBox(width: 6),
              IconButton.filled(
                tooltip: 'Send to coach',
                onPressed: _sending ? null : _send,
                icon: _sending
                    ? const SizedBox.square(
                        dimension: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.arrow_upward),
              ),
            ],
          ),
          if (_recording) ...[
            const SizedBox(height: 7),
            Row(
              children: [
                Icon(
                  Icons.graphic_eq,
                  size: 18,
                  color: Theme.of(context).colorScheme.error,
                ),
                const SizedBox(width: 6),
                Text(
                  'Listening… tap stop when you’re done',
                  style: Theme.of(context).textTheme.labelMedium?.copyWith(
                    color: Theme.of(context).colorScheme.error,
                  ),
                ),
              ],
            ),
          ],
          if (profile.memories.isNotEmpty) ...[
            const SizedBox(height: 22),
            Text(
              'What OpenNutri remembers',
              style: Theme.of(
                context,
              ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 4),
            Text(
              'Stored only on this device. Remove anything with one tap.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 7,
              children: [
                for (final memory in profile.memories)
                  InputChip(
                    avatar: const Icon(Icons.memory, size: 17),
                    label: Text(memory.fact),
                    onDeleted: () =>
                        widget.controller.removeCoachMemory(memory),
                  ),
              ],
            ),
          ],
          const SizedBox(height: 22),
          Text(
            'General guidance only. FDA adult Daily Values are broad comparison references, not individualized clinical targets.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}

class _DailyBrief extends StatelessWidget {
  const _DailyBrief({
    required this.enabled,
    required this.brief,
    required this.loading,
    required this.onActivate,
  });
  final bool enabled;
  final DailyCoachBrief? brief;
  final bool loading;
  final Future<bool> Function() onActivate;

  @override
  Widget build(BuildContext context) {
    final reply = brief?.reply;
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [scheme.tertiary, scheme.primary],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(26),
      ),
      child: DefaultTextStyle.merge(
        style: TextStyle(color: scheme.onPrimary),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                Icon(Icons.auto_awesome, color: Colors.white),
                SizedBox(width: 8),
                Text(
                  'DAILY SIGNAL',
                  style: TextStyle(
                    fontWeight: FontWeight.w900,
                    letterSpacing: 1,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 18),
            if (loading)
              const LinearProgressIndicator()
            else ...[
              Text(
                reply?.headline ?? 'Advice that knows your real day',
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  color: scheme.onPrimary,
                  fontWeight: FontWeight.w900,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                reply?.message ??
                    'Activate the coach once. After that, a fresh suggestion appears when you open OpenNutri.',
              ),
              if (!enabled) ...[
                const SizedBox(height: 16),
                FilledButton.tonal(
                  onPressed: onActivate,
                  child: const Text('Activate my coach'),
                ),
              ],
              if (reply?.actions.isNotEmpty ?? false) ...[
                const SizedBox(height: 14),
                for (final action in reply!.actions.take(3))
                  Padding(
                    padding: const EdgeInsets.only(top: 5),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(
                          Icons.arrow_forward,
                          size: 18,
                          color: Colors.white,
                        ),
                        const SizedBox(width: 7),
                        Expanded(child: Text(action.title)),
                      ],
                    ),
                  ),
              ],
              if (brief != null) ...[
                const SizedBox(height: 12),
                Text(
                  brief!.generatedByAi
                      ? 'Generated by ${reply?.model}'
                      : 'On-device fallback',
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: scheme.onPrimary.withValues(alpha: 0.75),
                  ),
                ),
              ],
            ],
          ],
        ),
      ),
    );
  }
}

class _ChatMessage {
  const _ChatMessage({
    required this.fromCoach,
    required this.text,
    this.remembered = const [],
  });
  final bool fromCoach;
  final String text;
  final List<CoachMemory> remembered;
}

class _ChatBubble extends StatelessWidget {
  const _ChatBubble({required this.message});
  final _ChatMessage message;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Align(
      alignment: message.fromCoach
          ? Alignment.centerLeft
          : Alignment.centerRight,
      child: Container(
        constraints: const BoxConstraints(maxWidth: 520),
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: message.fromCoach ? scheme.surface : scheme.primaryContainer,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(message.text),
            if (message.remembered.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                'Remembered: ${message.remembered.map((item) => item.fact).join(' · ')}',
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: scheme.primary,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
