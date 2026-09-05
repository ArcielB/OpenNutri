import 'package:flutter/material.dart';

import '../models/personalization.dart';

class DailyCoachCard extends StatelessWidget {
  const DailyCoachCard({
    super.key,
    required this.enabled,
    required this.brief,
    required this.loading,
    required this.onOpen,
  });

  final bool enabled;
  final DailyCoachBrief? brief;
  final bool loading;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final reply = brief?.reply;
    return Card(
      margin: const EdgeInsets.fromLTRB(16, 2, 16, 14),
      color: scheme.tertiaryContainer.withValues(alpha: 0.62),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onOpen,
        child: Padding(
          padding: const EdgeInsets.all(17),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: scheme.tertiary,
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(Icons.auto_awesome, color: scheme.onTertiary),
              ),
              const SizedBox(width: 13),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      enabled ? 'TODAY’S COACH' : 'PERSONAL AI COACH',
                      style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        fontWeight: FontWeight.w900,
                        letterSpacing: 1,
                        color: scheme.onTertiaryContainer,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      loading
                          ? 'Reading today’s nutrition…'
                          : reply?.headline ??
                                'Turn your real diary into one useful next step',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    if (!loading) ...[
                      const SizedBox(height: 3),
                      Text(
                        reply?.message ??
                            'Set a goal, choose a diet style, and tell OpenNutri what matters to you.',
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                      if (reply != null) ...[
                        const SizedBox(height: 5),
                        Text(
                          reply.sourceLabel,
                          style: Theme.of(context).textTheme.labelSmall,
                        ),
                      ],
                    ],
                  ],
                ),
              ),
              const Icon(Icons.chevron_right),
            ],
          ),
        ),
      ),
    );
  }
}
