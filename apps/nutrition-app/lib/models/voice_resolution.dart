import 'diary.dart';

class VoiceResolution {
  const VoiceResolution({
    required this.status,
    required this.metadata,
    required this.transcript,
    required this.detectedLanguage,
    required this.items,
    required this.manualSearchCandidates,
    this.manualSearchQuery,
    this.errorCode,
  });

  factory VoiceResolution.fromJson(Map<String, dynamic> json) {
    return VoiceResolution(
      status: json['status'] as String,
      metadata: ResolutionMetadata.fromJson(
        json['metadata'] as Map<String, dynamic>,
      ),
      transcript: json['transcript'] as String,
      detectedLanguage: json['detected_language'] as String,
      items: (json['items'] as List<dynamic>)
          .map(
            (value) =>
                ResolvedVoiceItem.fromJson(value as Map<String, dynamic>),
          )
          .toList(growable: false),
      manualSearchQuery: json['manual_search_query'] as String?,
      manualSearchCandidates:
          (json['manual_search_candidates'] as List<dynamic>)
              .map(
                (value) =>
                    VoiceFoodCandidate.fromJson(value as Map<String, dynamic>),
              )
              .toList(growable: false),
      errorCode: json['error_code'] as String?,
    );
  }

  final String status;
  final ResolutionMetadata metadata;
  final String transcript;
  final String detectedLanguage;
  final List<ResolvedVoiceItem> items;
  final String? manualSearchQuery;
  final List<VoiceFoodCandidate> manualSearchCandidates;
  final String? errorCode;

  bool get requiresManualSearch => status == 'manual_search';
}

class ResolutionMetadata {
  const ResolutionMetadata({
    required this.requestId,
    required this.coreVersion,
    required this.indexVersion,
    this.audioModel,
    this.extractionModel,
    this.selectorModel,
    this.embeddingModel,
  });

  factory ResolutionMetadata.fromJson(Map<String, dynamic> json) {
    return ResolutionMetadata(
      requestId: json['request_id'] as String,
      coreVersion: json['core_version'] as String,
      indexVersion: json['index_version'] as String,
      audioModel: json['audio_model'] as String?,
      extractionModel: json['extraction_model'] as String?,
      selectorModel: json['selector_model'] as String?,
      embeddingModel: json['embedding_model'] as String?,
    );
  }

  final String requestId;
  final String coreVersion;
  final String indexVersion;
  final String? audioModel;
  final String? extractionModel;
  final String? selectorModel;
  final String? embeddingModel;
}

class VoiceFoodCandidate {
  const VoiceFoodCandidate({
    required this.foodId,
    required this.name,
    required this.category,
    required this.qualityStatus,
    required this.sourceReleaseId,
    required this.portions,
    required this.hasUsableWeightFactor,
    required this.matchedChannels,
    required this.retrievalScore,
    this.matchedTerm,
    this.matchedTermType,
    this.primaryMatchTier,
    this.sourceTermExact = false,
  });

  factory VoiceFoodCandidate.fromJson(Map<String, dynamic> json) {
    return VoiceFoodCandidate(
      foodId: json['food_id'] as String,
      name: json['name'] as String,
      category: json['category'] as String,
      qualityStatus: json['quality_status'] as String,
      sourceReleaseId: json['source_release_id'] as String,
      portions: (json['portions'] as List<dynamic>)
          .map(
            (value) =>
                VoiceCandidatePortion.fromJson(value as Map<String, dynamic>),
          )
          .toList(growable: false),
      hasUsableWeightFactor: json['has_usable_weight_factor'] as bool,
      matchedChannels: (json['matched_channels'] as List<dynamic>)
          .cast<String>(),
      retrievalScore: (json['retrieval_score'] as num).toDouble(),
      matchedTerm: json['matched_term'] as String?,
      matchedTermType: json['matched_term_type'] as String?,
      primaryMatchTier: json['primary_match_tier'] as int?,
      sourceTermExact: json['source_term_exact'] as bool? ?? false,
    );
  }

  final String foodId;
  final String name;
  final String category;
  final String qualityStatus;
  final String sourceReleaseId;
  final List<VoiceCandidatePortion> portions;
  final bool hasUsableWeightFactor;
  final List<String> matchedChannels;
  final double retrievalScore;
  final String? matchedTerm;
  final String? matchedTermType;
  final int? primaryMatchTier;
  final bool sourceTermExact;
}

class VoiceCandidatePortion {
  const VoiceCandidatePortion({
    required this.portionId,
    required this.description,
    required this.gramWeight,
    this.amount,
  });

  factory VoiceCandidatePortion.fromJson(Map<String, dynamic> json) {
    return VoiceCandidatePortion(
      portionId: json['portion_id'] as String,
      description: json['description'] as String,
      gramWeight: (json['gram_weight'] as num).toDouble(),
      amount: (json['amount'] as num?)?.toDouble(),
    );
  }

  final String portionId;
  final String description;
  final double gramWeight;
  final double? amount;
}

class ResolvedVoiceItem {
  const ResolvedVoiceItem({
    required this.conceptIndex,
    required this.sourcePhrase,
    required this.selectedCandidate,
    required this.alternatives,
    required this.confidence,
    required this.preparation,
    required this.weightBasis,
    required this.quantity,
    required this.mealDefault,
    required this.unresolvedFields,
    required this.isUnspecified,
    this.autoLogEligible = false,
    this.noMatchReason,
  });

  factory ResolvedVoiceItem.fromJson(Map<String, dynamic> json) {
    final selected = json['selected_candidate'];
    return ResolvedVoiceItem(
      conceptIndex: json['concept_index'] as int,
      sourcePhrase: json['source_phrase'] as String,
      selectedCandidate: selected == null
          ? null
          : VoiceFoodCandidate.fromJson(selected as Map<String, dynamic>),
      alternatives: (json['alternatives'] as List<dynamic>)
          .map(
            (value) =>
                VoiceFoodCandidate.fromJson(value as Map<String, dynamic>),
          )
          .toList(growable: false),
      confidence: (json['confidence'] as num).toDouble(),
      preparation: (json['preparation'] as List<dynamic>).cast<String>(),
      weightBasis: VoiceWeightBasis.fromJson(
        json['weight_basis'] as Map<String, dynamic>,
      ),
      quantity: VoiceQuantity.fromJson(
        json['quantity'] as Map<String, dynamic>,
      ),
      mealDefault: MealType.values.byName(json['meal_default'] as String),
      unresolvedFields: (json['unresolved_fields'] as List<dynamic>)
          .cast<String>(),
      isUnspecified: json['is_unspecified'] as bool,
      autoLogEligible: json['auto_log_eligible'] as bool? ?? false,
      noMatchReason: json['no_match_reason'] as String?,
    );
  }

  final int conceptIndex;
  final String sourcePhrase;
  final VoiceFoodCandidate? selectedCandidate;
  final List<VoiceFoodCandidate> alternatives;
  final double confidence;
  final List<String> preparation;
  final VoiceWeightBasis weightBasis;
  final VoiceQuantity quantity;
  final MealType mealDefault;
  final List<String> unresolvedFields;
  final bool isUnspecified;
  final bool autoLogEligible;
  final String? noMatchReason;

  List<VoiceFoodCandidate> get candidates {
    final values = <VoiceFoodCandidate>[?selectedCandidate, ...alternatives];
    final seen = <String>{};
    return values.where((value) => seen.add(value.foodId)).toList();
  }
}

class VoiceWeightBasis {
  const VoiceWeightBasis({required this.status, this.value});

  factory VoiceWeightBasis.fromJson(Map<String, dynamic> json) {
    return VoiceWeightBasis(
      status: json['status'] as String,
      value: switch (json['value'] as String?) {
        'edible' => LoggedWeightBasis.edible,
        'as_purchased' => LoggedWeightBasis.asPurchased,
        _ => null,
      },
    );
  }

  final String status;
  final LoggedWeightBasis? value;
}

class VoiceQuantity {
  const VoiceQuantity({
    required this.status,
    this.grams,
    this.spokenValue,
    this.spokenUnit,
    this.sourcePortionId,
    this.sourcePortionDescription,
  });

  factory VoiceQuantity.fromJson(Map<String, dynamic> json) {
    return VoiceQuantity(
      status: json['status'] as String,
      grams: (json['grams'] as num?)?.toDouble(),
      spokenValue: (json['spoken_value'] as num?)?.toDouble(),
      spokenUnit: json['spoken_unit'] as String?,
      sourcePortionId: json['source_portion_id'] as String?,
      sourcePortionDescription: json['source_portion_description'] as String?,
    );
  }

  final String status;
  final double? grams;
  final double? spokenValue;
  final String? spokenUnit;
  final String? sourcePortionId;
  final String? sourcePortionDescription;
}

class VoiceFeedbackItem {
  const VoiceFeedbackItem({
    required this.sourcePhrase,
    required this.proposedFoodId,
    required this.finalFoodId,
    required this.corrected,
  });

  final String sourcePhrase;
  final String? proposedFoodId;
  final String finalFoodId;
  final bool corrected;

  Map<String, dynamic> toJson() => {
    'source_phrase': sourcePhrase,
    'proposed_food_id': proposedFoodId,
    'final_food_id': finalFoodId,
    'corrected': corrected,
  };
}
