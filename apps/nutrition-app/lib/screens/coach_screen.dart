import 'dart:async';

import 'package:flutter/material.dart';

import '../models/personalization.dart';
import '../services/coach_service.dart';
import '../services/voice_recorder.dart';
import '../services/voice_api_client.dart';
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
    this.isActive = true,
  });

  final AppController controller;
  final CoachService coachService;
  final Future<void> Function({bool force}) refreshDaily;
  final bool dailyLoading;
  final bool isActive;

  @override
  State<CoachScreen> createState() => _CoachScreenState();
}

class _CoachScreenState extends State<CoachScreen> with WidgetsBindingObserver {
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
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void didUpdateWidget(covariant CoachScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!widget.isActive && _recording) _cancelVoice();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused && _recording) _cancelVoice();
  }

  void _cancelVoice() {
    _recording = false;
    unawaited(_recorder.cancel());
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _recorder.removeListener(_onRecorderChanged);
    unawaited(_recorder.cancel().whenComplete(_recorder.dispose));
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
          'Your goal, diet notes, saved facts, messages, and a summary of the selected diary day are sent to Google Gemini for advice. Voice messages also send a temporary recording, deleted from this phone after the request. OpenNutri’s server does not store these requests or replies.\n\nThis beta uses Gemini’s unpaid service. Google may use inputs and replies to improve its products, and human reviewers may review them. Avoid confidential or sensitive information. You can disable coaching in Settings.\n\nThis is general food guidance, not medical care.',
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
    if (accepted != true || !mounted) return false;
    await widget.controller.enableCoach();
    await widget.refreshDaily(force: true);
    return true;
  }

  Future<void> _send() async {
    final text = _message.text.trim();
    if (text.isEmpty || text.length > 1000 || _sending || _recording) return;
    if (!await _ensureEnabled() || !mounted || _sending) return;
    final conversation = _conversation;
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
        conversation: conversation,
      );
      if (!widget.controller.profile.coachEnabled) return;
      await widget.controller.addCoachMemories(reply.memoryUpdates);
      if (!mounted) return;
      setState(() {
        _messages.add(
          _ChatMessage(
            fromCoach: true,
            text: _replyText(reply.message, reply.safetyNote),
            model: reply.model,
            remembered: reply.memoryUpdates,
          ),
        );
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _messages.add(
          _ChatMessage(fromCoach: true, text: _errorMessage(error)),
        );
      });
      _message.text = text;
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
        conversation: _conversation,
      );
      if (!widget.controller.profile.coachEnabled) return;
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
            text: _replyText(reply.message, reply.safetyNote),
            model: reply.model,
            remembered: reply.memoryUpdates,
          ),
        );
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _messages.add(
          _ChatMessage(
            fromCoach: true,
            text:
                error is VoiceApiException &&
                    error.kind == VoiceApiFailureKind.rateLimited
                ? 'The AI request limit has been reached. Please try again later. '
                      'The recording was deleted and nothing was remembered.'
                : 'I couldn’t finish that voice message. The recording was deleted and nothing was remembered.',
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

  String _replyText(String message, String? note) =>
      note == null || note.trim().isEmpty ? message : '$message\n\n$note';

  List<Map<String, String>> get _conversation => _messages
      .skip(1)
      .toList()
      .reversed
      .take(6)
      .toList()
      .reversed
      .map(
        (message) => {
          'role': message.fromCoach ? 'assistant' : 'user',
          'text': message.text.length <= 1000
              ? message.text
              : message.text.substring(0, 1000),
        },
      )
      .toList();

  String _errorMessage(Object error) =>
      error is VoiceApiException &&
          error.kind == VoiceApiFailureKind.rateLimited
      ? 'The shared AI limit has been reached. Your message is ready to retry later.'
      : 'The coach could not finish. Your message is ready to retry; no new facts were saved.';

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
                  maxLength: 1000,
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
                onPressed: _sending || _recording ? null : _send,
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
                    (enabled
                        ? 'Refresh for advice based on the selected day.'
                        : 'Activate the coach once. After that, a daily suggestion appears when you open OpenNutri.'),
              ),
              if (reply?.safetyNote?.isNotEmpty ?? false) ...[
                const SizedBox(height: 8),
                Text(reply!.safetyNote!),
              ],
              if (reply != null) ...[
                const SizedBox(height: 8),
                Text(reply.sourceLabel, style: const TextStyle(fontSize: 12)),
              ],
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
                      ? '${brief!.dateKey} · AI advice from your saved snapshot'
                      : '${brief!.dateKey} · On-device fallback',
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
    this.model,
  });
  final bool fromCoach;
  final String text;
  final List<CoachMemory> remembered;
  final String? model;
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
            if (message.model != null) ...[
              const SizedBox(height: 6),
              Text(
                'AI model: ${message.model}',
                style: Theme.of(context).textTheme.labelSmall,
              ),
            ],
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
