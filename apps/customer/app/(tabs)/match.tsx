// app/(tabs)/match.tsx
import { useCallback, useRef, useState } from "react";
import {
  View, Text, ScrollView, Pressable, TextInput,
  ActivityIndicator, Modal, Alert, StyleSheet,
} from "react-native";
import { useFocusEffect } from "expo-router";
import { apiFetch } from "@/lib/api";
import type { InstructorPublicRead, MatchRequestRead, MatchRequestType, UserRead } from "@/types/api";

const NAMED_FEE = 5_000;

const PURPOSES = [
  { label: "스윙 교정",    emoji: "🏌️", specialty: "스윙 교정" },
  { label: "비거리 향상",  emoji: "💪", specialty: "비거리 향상" },
  { label: "퍼팅 & 숏게임", emoji: "⛳", specialty: "퍼팅" },
  { label: "초보자 입문",  emoji: "🌱", specialty: "초보자 맞춤" },
  { label: "코스 전략",    emoji: "🗺️", specialty: "코스 매니지먼트" },
  { label: "멘탈 관리",    emoji: "🧠", specialty: "멘탈 코칭" },
];

const LOCATIONS = ["서울", "경기", "인천", "부산", "대구", "대전", "광주", "기타"];

const STATUS_COLOR: Record<string, string> = {
  PENDING: "#f59e0b", ACCEPTED: "#10b981", REJECTED: "#ef4444", CANCELLED: "#9ca3af",
};
const STATUS_LABEL: Record<string, string> = {
  PENDING: "승인 대기 중", ACCEPTED: "연결 완료", REJECTED: "거절됨", CANCELLED: "취소됨",
};
const TYPE_LABEL: Record<MatchRequestType, string> = {
  MATCH: "매칭",
  CONSULTATION: "상담",
};

type TabType = "recommend" | "search";

export default function MatchScreen() {
  const [tab, setTab] = useState<TabType>("recommend");

  const [instructors, setInstructors] = useState<InstructorPublicRead[]>([]);
  const [myRequests, setMyRequests]   = useState<MatchRequestRead[]>([]);
  const [me, setMe]                   = useState<UserRead | null>(null);
  const [loading, setLoading]         = useState(true);
  const initialLoaded                 = useRef(false);

  // 숨고식 단계별 매칭 wizard
  const [wizStep, setWizStep]           = useState(0);           // 0=purpose 1=location 2=results
  const [wizPurpose, setWizPurpose]     = useState<typeof PURPOSES[0] | null>(null);
  const [wizLocation, setWizLocation]   = useState<string | null>(null);

  // 강사 찾기 검색어
  const [searchText, setSearchText] = useState("");

  // 신청 모달
  const [selectedInstructor, setSelectedInstructor] = useState<InstructorPublicRead | null>(null);
  const [requestType, setRequestType] = useState<MatchRequestType>("MATCH");
  const [note, setNote]         = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function load() {
    try {
      const [meData, instrList, requests] = await Promise.all([
        apiFetch<UserRead>("/users/me"),
        apiFetch<InstructorPublicRead[]>("/instructors/public"),
        apiFetch<MatchRequestRead[]>("/instructors/match/me"),
      ]);
      setMe(meData);
      setInstructors(instrList);
      setMyRequests(requests);
    } catch (e) {
      console.error("강사 정보 로딩 실패:", e);
    } finally {
      setLoading(false);
      initialLoaded.current = true;
    }
  }

  useFocusEffect(useCallback(() => {
    if (!initialLoaded.current) setLoading(true);
    load();
  }, []));

  // 활성 요청 (각 타입별로 PENDING/ACCEPTED 중 최신)
  const activeMatchReq = myRequests.find(
    r => r.request_type === "MATCH" && (r.status === "PENDING" || r.status === "ACCEPTED")
  ) ?? null;
  const activeConsultReq = myRequests.find(
    r => r.request_type === "CONSULTATION" && (r.status === "PENDING" || r.status === "ACCEPTED")
  ) ?? null;

  // 필터링
  const wizResults = instructors.filter(i => {
    if (wizLocation && i.location !== wizLocation) return false;
    if (wizPurpose && !i.specialties.includes(wizPurpose.specialty)) return false;
    return true;
  });

  const searchList = instructors.filter(i =>
    searchText.trim() === "" ||
    i.display_name.toLowerCase().includes(searchText.toLowerCase()) ||
    i.username.toLowerCase().includes(searchText.toLowerCase())
  );

  const isMatched = !!me?.manager_id;
  const hasMatchPending = activeMatchReq?.status === "PENDING";
  const hasConsultPending = activeConsultReq?.status === "PENDING";

  // 매칭 or 상담 신청 공통 함수
  function openModal(instructor: InstructorPublicRead, type: MatchRequestType) {
    setSelectedInstructor(instructor);
    setRequestType(type);
    setNote("");
  }

  async function submitRequest() {
    if (!selectedInstructor) return;
    setSubmitting(true);
    try {
      const res = await apiFetch<MatchRequestRead>("/instructors/match", {
        method: "POST",
        body: {
          instructor_id: selectedInstructor.id,
          note: note.trim() || undefined,
          request_type: requestType,
        },
      });
      setMyRequests(prev => [res, ...prev]);
      setSelectedInstructor(null);
      setNote("");
      const label = requestType === "MATCH" ? "매칭 신청" : "상담 신청";
      const desc = requestType === "MATCH"
        ? "강사 수락 후 담당 강사로 연결됩니다."
        : "강사가 확인 후 연락드립니다.";
      Alert.alert("완료", `${label}이 완료되었습니다.\n${desc}`);
    } catch (e: any) {
      const msg = e?.body?.detail ?? e?.message ?? "신청 실패";
      Alert.alert("오류", typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setSubmitting(false);
    }
  }

  async function cancelRequest(req: MatchRequestRead) {
    const label = TYPE_LABEL[req.request_type];
    Alert.alert(`${label} 취소`, `${label} 신청을 취소하시겠습니까?`, [
      { text: "아니요", style: "cancel" },
      {
        text: "취소하기", style: "destructive",
        onPress: async () => {
          try {
            await apiFetch(`/instructors/match/${req.id}`, { method: "DELETE" });
            setMyRequests(prev => prev.filter(r => r.id !== req.id));
          } catch (e: any) {
            Alert.alert("오류", e?.message ?? "취소 실패");
          }
        },
      },
    ]);
  }

  function resetWizard() {
    setWizStep(0);
    setWizPurpose(null);
    setWizLocation(null);
  }

  if (loading) return <View style={s.center}><ActivityIndicator size="large" /></View>;

  return (
    <View style={{ flex: 1, backgroundColor: "#f9fafb" }}>

      {/* 현재 매칭 상태 배너 */}
      {activeMatchReq && (
        <RequestBanner
          req={activeMatchReq}
          onCancel={() => cancelRequest(activeMatchReq)}
        />
      )}
      {activeConsultReq && (
        <RequestBanner
          req={activeConsultReq}
          onCancel={() => cancelRequest(activeConsultReq)}
        />
      )}

      {/* 탭 전환 */}
      <View style={s.tabBar}>
        <Pressable
          style={[s.tabBtn, tab === "recommend" && s.tabBtnActive]}
          onPress={() => setTab("recommend")}
        >
          <Text style={[s.tabTxt, tab === "recommend" && s.tabTxtActive]}>강사 매칭</Text>
        </Pressable>
        <Pressable
          style={[s.tabBtn, tab === "search" && s.tabBtnActive]}
          onPress={() => setTab("search")}
        >
          <Text style={[s.tabTxt, tab === "search" && s.tabTxtActive]}>강사 찾기</Text>
        </Pressable>
      </View>

      {tab === "recommend" ? (
        <WizardFlow
          step={wizStep}
          purpose={wizPurpose}
          location={wizLocation}
          results={wizResults}
          totalCount={instructors.length}
          isMatched={isMatched}
          hasMatchPending={hasMatchPending}
          hasConsultPending={hasConsultPending}
          me={me}
          onSelectPurpose={(p) => { setWizPurpose(p); setWizStep(1); }}
          onSelectLocation={(l) => { setWizLocation(l); setWizStep(2); }}
          onBack={() => setWizStep(s => Math.max(0, s - 1))}
          onReset={resetWizard}
          onSelectMatch={(i) => openModal(i, "MATCH")}
          onSelectConsult={(i) => openModal(i, "CONSULTATION")}
        />
      ) : (
        <SearchTab
          instructors={searchList}
          searchText={searchText}
          onSearchChange={setSearchText}
          isMatched={isMatched}
          hasMatchPending={hasMatchPending}
          hasConsultPending={hasConsultPending}
          me={me}
          onSelectMatch={(i) => openModal(i, "MATCH")}
          onSelectConsult={(i) => openModal(i, "CONSULTATION")}
        />
      )}

      {/* 신청 모달 */}
      <RequestModal
        instructor={selectedInstructor}
        requestType={requestType}
        note={note}
        submitting={submitting}
        onNoteChange={setNote}
        onClose={() => setSelectedInstructor(null)}
        onSubmit={submitRequest}
      />
    </View>
  );
}

// ── 요청 상태 배너 ─────────────────────────────────────────────
function RequestBanner({ req, onCancel }: { req: MatchRequestRead; onCancel: () => void }) {
  const typeLabel = TYPE_LABEL[req.request_type];
  const statusLabel = `[${typeLabel}] ${STATUS_LABEL[req.status]}`;
  return (
    <View style={[s.statusBanner, { borderLeftColor: STATUS_COLOR[req.status] }]}>
      <View style={{ flex: 1 }}>
        <Text style={s.statusLabel}>{statusLabel}</Text>
        <Text style={s.statusSub}>
          {req.instructor_name ?? "강사"}
          {req.fee > 0 ? `  ·  수수료 ${req.fee.toLocaleString()}원` : ""}
        </Text>
        {req.note ? <Text style={s.statusNote}>"{req.note}"</Text> : null}
      </View>
      {req.status === "PENDING" && (
        <Pressable style={s.cancelBtn} onPress={onCancel}>
          <Text style={s.cancelBtnTxt}>취소</Text>
        </Pressable>
      )}
    </View>
  );
}

// ── 숨고식 단계별 매칭 ────────────────────────────────────────
function WizardFlow({
  step, purpose, location, results, totalCount,
  isMatched, hasMatchPending, hasConsultPending, me,
  onSelectPurpose, onSelectLocation, onBack, onReset,
  onSelectMatch, onSelectConsult,
}: {
  step: number;
  purpose: typeof PURPOSES[0] | null;
  location: string | null;
  results: InstructorPublicRead[];
  totalCount: number;
  isMatched: boolean;
  hasMatchPending: boolean;
  hasConsultPending: boolean;
  me: UserRead | null;
  onSelectPurpose: (p: typeof PURPOSES[0]) => void;
  onSelectLocation: (l: string) => void;
  onBack: () => void;
  onReset: () => void;
  onSelectMatch: (i: InstructorPublicRead) => void;
  onSelectConsult: (i: InstructorPublicRead) => void;
}) {
  if (step === 0) {
    return (
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={wz.container}>
        <Text style={wz.stepHint}>STEP 1 / 2</Text>
        <Text style={wz.title}>어떤 레슨을 받고{"\n"}싶으신가요?</Text>
        <Text style={wz.subtitle}>목적에 맞는 강사를 추천해 드립니다</Text>
        <View style={wz.purposeGrid}>
          {PURPOSES.map(p => (
            <Pressable key={p.label} style={wz.purposeCard} onPress={() => onSelectPurpose(p)}>
              <Text style={wz.purposeEmoji}>{p.emoji}</Text>
              <Text style={wz.purposeLabel}>{p.label}</Text>
            </Pressable>
          ))}
        </View>
        <View style={{ height: 40 }} />
      </ScrollView>
    );
  }

  if (step === 1) {
    return (
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={wz.container}>
        <Pressable style={wz.backRow} onPress={onBack}>
          <Text style={wz.backTxt}>← 이전</Text>
        </Pressable>
        <Text style={wz.stepHint}>STEP 2 / 2</Text>
        <Text style={wz.title}>어디서 레슨을 받고{"\n"}싶으신가요?</Text>
        {purpose && (
          <View style={wz.selectedChip}>
            <Text style={wz.selectedChipTxt}>{purpose.emoji} {purpose.label}</Text>
          </View>
        )}
        <View style={wz.locationGrid}>
          {LOCATIONS.map(loc => (
            <Pressable
              key={loc}
              style={[wz.locationCard, location === loc && wz.locationCardActive]}
              onPress={() => onSelectLocation(loc)}
            >
              <Text style={[wz.locationTxt, location === loc && wz.locationTxtActive]}>
                {loc}
              </Text>
            </Pressable>
          ))}
        </View>
        <View style={{ height: 40 }} />
      </ScrollView>
    );
  }

  // Step 2 = results
  return (
    <ScrollView showsVerticalScrollIndicator={false}>
      <View style={wz.resultsHeader}>
        <Pressable onPress={onBack}>
          <Text style={wz.backTxt}>← 이전</Text>
        </Pressable>
        <View style={wz.filterSummary}>
          {purpose && <View style={wz.filterChip}><Text style={wz.filterChipTxt}>{purpose.label}</Text></View>}
          {location && <View style={wz.filterChip}><Text style={wz.filterChipTxt}>📍 {location}</Text></View>}
        </View>
        <Pressable onPress={onReset}>
          <Text style={wz.resetTxt}>초기화</Text>
        </Pressable>
      </View>

      <Text style={wz.resultCount}>
        {results.length > 0
          ? `추천 강사 ${results.length}명`
          : totalCount > 0 ? "조건에 맞는 강사가 없어요" : "등록된 강사가 없습니다"}
      </Text>

      {results.length === 0 ? (
        <View style={wz.emptyBox}>
          <Text style={wz.emptyEmoji}>🔍</Text>
          <Text style={wz.emptyTitle}>조건에 맞는 강사가 없어요</Text>
          <Text style={wz.emptySub}>다른 지역이나 목적으로 다시 찾아보세요</Text>
          <Pressable style={wz.emptyBtn} onPress={onReset}>
            <Text style={wz.emptyBtnTxt}>처음부터 다시</Text>
          </Pressable>
        </View>
      ) : (
        results.map(i => (
          <InstructorCard
            key={i.id}
            instructor={i}
            isMatched={isMatched}
            hasMatchPending={hasMatchPending}
            hasConsultPending={hasConsultPending}
            isCurrentInstructor={me?.manager_id === i.id}
            onMatchPress={() => onSelectMatch(i)}
            onConsultPress={() => onSelectConsult(i)}
          />
        ))
      )}
      <View style={{ height: 40 }} />
    </ScrollView>
  );
}

// ── 강사 찾기 탭 ─────────────────────────────────────────────
function SearchTab({
  instructors, searchText, onSearchChange,
  isMatched, hasMatchPending, hasConsultPending, me,
  onSelectMatch, onSelectConsult,
}: {
  instructors: InstructorPublicRead[];
  searchText: string;
  onSearchChange: (v: string) => void;
  isMatched: boolean;
  hasMatchPending: boolean;
  hasConsultPending: boolean;
  me: UserRead | null;
  onSelectMatch: (i: InstructorPublicRead) => void;
  onSelectConsult: (i: InstructorPublicRead) => void;
}) {
  return (
    <ScrollView showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled">
      <View style={se.searchBox}>
        <Text style={se.searchIcon}>🔍</Text>
        <TextInput
          style={se.searchInput}
          value={searchText}
          onChangeText={onSearchChange}
          placeholder="강사 이름으로 검색"
          placeholderTextColor="#9ca3af"
          returnKeyType="search"
        />
        {searchText.length > 0 && (
          <Pressable onPress={() => onSearchChange("")}>
            <Text style={se.clearBtn}>✕</Text>
          </Pressable>
        )}
      </View>

      <Text style={se.resultCount}>
        {searchText ? `"${searchText}" 검색 결과 ${instructors.length}명` : `전체 강사 ${instructors.length}명`}
      </Text>

      {instructors.length === 0 ? (
        <Text style={s.empty}>
          {searchText ? `"${searchText}"에 해당하는 강사가 없습니다.` : "등록된 강사가 없습니다."}
        </Text>
      ) : (
        instructors.map(i => (
          <InstructorCard
            key={i.id}
            instructor={i}
            isMatched={isMatched}
            hasMatchPending={hasMatchPending}
            hasConsultPending={hasConsultPending}
            isCurrentInstructor={me?.manager_id === i.id}
            onMatchPress={() => onSelectMatch(i)}
            onConsultPress={() => onSelectConsult(i)}
          />
        ))
      )}
      <View style={{ height: 40 }} />
    </ScrollView>
  );
}

// ── 강사 카드 ────────────────────────────────────────────────
function InstructorCard({
  instructor, isMatched, hasMatchPending, hasConsultPending,
  isCurrentInstructor, onMatchPress, onConsultPress,
}: {
  instructor: InstructorPublicRead;
  isMatched: boolean;
  hasMatchPending: boolean;
  hasConsultPending: boolean;
  isCurrentInstructor: boolean;
  onMatchPress: () => void;
  onConsultPress: () => void;
}) {
  const isNamed = instructor.instructor_tier === "NAMED";
  const matchDisabled = isMatched || hasMatchPending;
  const consultDisabled = hasConsultPending;

  return (
    <View style={[c.card, isCurrentInstructor && c.currentCard]}>
      <View style={c.top}>
        <View style={[c.avatar, isNamed && c.namedAvatar]}>
          <Text style={[c.avatarTxt, isNamed && c.namedAvatarTxt]}>
            {instructor.display_name.charAt(0)}
          </Text>
        </View>
        <View style={{ flex: 1 }}>
          <View style={c.nameRow}>
            <Text style={c.name}>{instructor.display_name}</Text>
            <View style={[c.tierBadge, isNamed && c.namedBadge]}>
              <Text style={[c.tierTxt, isNamed && c.namedTxt]}>
                {isNamed ? "Named" : "Normal"}
              </Text>
            </View>
          </View>
          <Text style={c.username}>@{instructor.username}</Text>
          {instructor.location && (
            <Text style={c.location}>📍 {instructor.location}</Text>
          )}
        </View>
      </View>

      {instructor.bio ? (
        <Text style={c.bio} numberOfLines={2}>{instructor.bio}</Text>
      ) : null}

      {instructor.specialties.length > 0 && (
        <View style={c.tagsRow}>
          {instructor.specialties.map(sp => (
            <View key={sp} style={c.tag}>
              <Text style={c.tagTxt}>{sp}</Text>
            </View>
          ))}
        </View>
      )}

      <View style={c.bottom}>
        <View>
          <Text style={c.feeLabel}>매칭 수수료</Text>
          <Text style={[c.feeValue, isNamed && c.namedFee]}>
            {isNamed ? `${NAMED_FEE.toLocaleString()}원` : "무료"}
          </Text>
        </View>

        {isCurrentInstructor ? (
          <View style={c.currentBadge}>
            <Text style={c.currentBadgeTxt}>담당 강사</Text>
          </View>
        ) : (
          <View style={c.btnRow}>
            {/* 상담 신청 — 항상 무료, 매칭과 독립 */}
            <Pressable
              style={[c.consultBtn, consultDisabled && c.btnDisabled]}
              onPress={onConsultPress}
              disabled={consultDisabled}
            >
              <Text style={[c.consultBtnTxt, consultDisabled && c.btnTxtDisabled]}>
                {consultDisabled ? "상담 중" : "상담 신청"}
              </Text>
            </Pressable>
            {/* 매칭 신청 */}
            <Pressable
              style={[c.matchBtn, matchDisabled && c.btnDisabled]}
              onPress={onMatchPress}
              disabled={matchDisabled}
            >
              <Text style={[c.matchBtnTxt, matchDisabled && c.btnTxtDisabled]}>
                {isMatched ? "매칭 완료" : hasMatchPending ? "대기 중" : "매칭 신청"}
              </Text>
            </Pressable>
          </View>
        )}
      </View>
    </View>
  );
}

// ── 신청 모달 (매칭 / 상담 공용) ─────────────────────────────
function RequestModal({
  instructor, requestType, note, submitting,
  onNoteChange, onClose, onSubmit,
}: {
  instructor: InstructorPublicRead | null;
  requestType: MatchRequestType;
  note: string;
  submitting: boolean;
  onNoteChange: (v: string) => void;
  onClose: () => void;
  onSubmit: () => void;
}) {
  if (!instructor) return null;
  const isNamed = instructor.instructor_tier === "NAMED";
  const isConsultation = requestType === "CONSULTATION";
  const title = isConsultation ? "상담 신청" : "매칭 신청";
  // 상담은 항상 무료
  const showFee = !isConsultation && isNamed;

  return (
    <Modal visible animationType="slide" presentationStyle="pageSheet" onRequestClose={onClose}>
      <View style={m.container}>
        <View style={m.header}>
          <Text style={m.title}>{title}</Text>
          <Pressable onPress={onClose} style={m.closeBtn}>
            <Text style={m.closeTxt}>✕</Text>
          </Pressable>
        </View>

        <ScrollView showsVerticalScrollIndicator={false}>
          <View style={m.instrCard}>
            <View style={[m.avatar, isNamed && m.namedAvatar]}>
              <Text style={[m.avatarTxt, isNamed && m.namedAvatarTxt]}>
                {instructor.display_name.charAt(0)}
              </Text>
            </View>
            <View style={[m.tierBadge, isNamed && m.namedBadge]}>
              <Text style={[m.tierTxt, isNamed && m.namedTxt]}>
                {isNamed ? "Named" : "Normal"}
              </Text>
            </View>
            <Text style={m.instrName}>{instructor.display_name}</Text>
            {instructor.location && <Text style={m.instrSub}>📍 {instructor.location}</Text>}
          </View>

          {isConsultation ? (
            <View style={[m.feeBox, m.consultBox]}>
              <Text style={m.consultTitle}>💬 무료 상담</Text>
              <Text style={m.feeNote}>
                궁금한 점을 메모에 남겨주세요.{"\n"}강사가 확인 후 연락드립니다.{"\n"}담당 강사 연결과 무관합니다.
              </Text>
            </View>
          ) : showFee ? (
            <View style={m.feeBox}>
              <Text style={m.feeLabel}>매칭 수수료</Text>
              <Text style={m.feeAmount}>{NAMED_FEE.toLocaleString()}원</Text>
              <Text style={m.feeNote}>네임드 강사 매칭 시 고객이 수수료를 부담합니다.{"\n"}수락 후 결제가 진행됩니다.</Text>
            </View>
          ) : (
            <View style={[m.feeBox, m.freeBox]}>
              <Text style={m.freeTxt}>무료 매칭</Text>
              <Text style={m.feeNote}>이 강사는 수수료 없이 매칭할 수 있습니다.</Text>
            </View>
          )}

          <Text style={m.label}>
            {isConsultation ? "상담 내용 (선택)" : "강사에게 남길 메모 (선택)"}
          </Text>
          <TextInput
            value={note}
            onChangeText={onNoteChange}
            placeholder={
              isConsultation
                ? "예: 주 2회 레슨 가능한지, 비용이 궁금합니다."
                : "예: 초보자입니다. 드라이버 교정이 필요합니다."
            }
            multiline
            numberOfLines={3}
            style={m.input}
          />

          <View style={m.btns}>
            <Pressable style={m.cancelBtn} onPress={onClose}>
              <Text style={m.cancelTxt}>취소</Text>
            </Pressable>
            <Pressable
              style={[m.submitBtn, submitting && { opacity: 0.6 }, isConsultation && m.consultSubmitBtn]}
              onPress={onSubmit}
              disabled={submitting}
            >
              <Text style={m.submitTxt}>{submitting ? "신청 중..." : title}</Text>
            </Pressable>
          </View>
        </ScrollView>
      </View>
    </Modal>
  );
}

// ── 스타일 ────────────────────────────────────────────────────
const s = StyleSheet.create({
  center:       { flex: 1, alignItems: "center", justifyContent: "center" },
  statusBanner: {
    marginHorizontal: 16, marginTop: 8, backgroundColor: "#fff", borderRadius: 14,
    borderLeftWidth: 4, padding: 16,
    flexDirection: "row", alignItems: "center",
    shadowColor: "#000", shadowOpacity: 0.06, shadowRadius: 8, elevation: 2,
  },
  statusLabel:  { fontSize: 15, fontWeight: "700", color: "#111", marginBottom: 2 },
  statusSub:    { fontSize: 13, color: "#6b7280" },
  statusNote:   { fontSize: 12, color: "#9ca3af", marginTop: 4, fontStyle: "italic" },
  cancelBtn:    { paddingHorizontal: 12, paddingVertical: 6, backgroundColor: "#fee2e2", borderRadius: 8 },
  cancelBtnTxt: { fontSize: 13, color: "#ef4444", fontWeight: "600" },
  tabBar:       { flexDirection: "row", margin: 16, marginTop: 12, backgroundColor: "#f3f4f6", borderRadius: 12, padding: 4 },
  tabBtn:       { flex: 1, paddingVertical: 9, borderRadius: 9, alignItems: "center" },
  tabBtnActive: { backgroundColor: "#fff", shadowColor: "#000", shadowOpacity: 0.08, shadowRadius: 4, elevation: 2 },
  tabTxt:       { fontSize: 14, fontWeight: "600", color: "#9ca3af" },
  tabTxtActive: { color: "#111" },
  empty:        { textAlign: "center", color: "#9ca3af", fontSize: 14, marginTop: 40 },
});

// wizard styles
const wz = StyleSheet.create({
  container:   { padding: 20 },
  backRow:     { marginBottom: 8 },
  backTxt:     { fontSize: 14, color: "#6b7280", fontWeight: "500" },
  stepHint:    { fontSize: 12, color: "#9ca3af", fontWeight: "700", marginBottom: 8, letterSpacing: 1 },
  title:       { fontSize: 26, fontWeight: "800", color: "#111", lineHeight: 34, marginBottom: 6 },
  subtitle:    { fontSize: 14, color: "#6b7280", marginBottom: 24 },
  purposeGrid: { flexDirection: "row", flexWrap: "wrap", gap: 12 },
  purposeCard: {
    width: "47%", backgroundColor: "#fff", borderRadius: 16,
    padding: 20, alignItems: "center",
    shadowColor: "#000", shadowOpacity: 0.05, shadowRadius: 8, elevation: 2,
    borderWidth: 1, borderColor: "#f3f4f6",
  },
  purposeEmoji: { fontSize: 32, marginBottom: 10 },
  purposeLabel: { fontSize: 14, fontWeight: "700", color: "#111", textAlign: "center" },
  selectedChip: {
    alignSelf: "flex-start", backgroundColor: "#e0e7ff",
    borderRadius: 20, paddingHorizontal: 14, paddingVertical: 6, marginBottom: 20,
  },
  selectedChipTxt: { fontSize: 13, fontWeight: "600", color: "#4f46e5" },
  locationGrid:    { flexDirection: "row", flexWrap: "wrap", gap: 10, marginTop: 4 },
  locationCard:    {
    width: "22%", minWidth: 72, backgroundColor: "#fff",
    borderRadius: 12, paddingVertical: 16, alignItems: "center",
    borderWidth: 1.5, borderColor: "#e5e7eb",
    shadowColor: "#000", shadowOpacity: 0.04, shadowRadius: 4, elevation: 1,
  },
  locationCardActive: { backgroundColor: "#1a1a1a", borderColor: "#1a1a1a" },
  locationTxt:        { fontSize: 14, fontWeight: "600", color: "#374151" },
  locationTxtActive:  { color: "#fff" },
  resultsHeader:  {
    flexDirection: "row", alignItems: "center",
    paddingHorizontal: 16, paddingVertical: 12, gap: 8,
  },
  filterSummary:  { flex: 1, flexDirection: "row", gap: 6, flexWrap: "wrap" },
  filterChip:     { backgroundColor: "#e0e7ff", borderRadius: 20, paddingHorizontal: 10, paddingVertical: 4 },
  filterChipTxt:  { fontSize: 12, fontWeight: "600", color: "#4f46e5" },
  resetTxt:       { fontSize: 12, color: "#9ca3af" },
  resultCount:    { fontSize: 13, fontWeight: "600", color: "#6b7280", paddingHorizontal: 16, marginBottom: 4 },
  emptyBox:       { alignItems: "center", paddingVertical: 60, paddingHorizontal: 24 },
  emptyEmoji:     { fontSize: 48, marginBottom: 16 },
  emptyTitle:     { fontSize: 17, fontWeight: "700", color: "#374151", marginBottom: 6 },
  emptySub:       { fontSize: 13, color: "#9ca3af", textAlign: "center", marginBottom: 24 },
  emptyBtn:       { backgroundColor: "#1a1a1a", paddingHorizontal: 24, paddingVertical: 12, borderRadius: 10 },
  emptyBtnTxt:    { color: "#fff", fontWeight: "700" },
});

const se = StyleSheet.create({
  searchBox:   { flexDirection: "row", alignItems: "center", margin: 16, backgroundColor: "#fff", borderRadius: 12, paddingHorizontal: 14, paddingVertical: 10, borderWidth: 1, borderColor: "#e5e7eb" },
  searchIcon:  { fontSize: 16, marginRight: 8 },
  searchInput: { flex: 1, fontSize: 15, color: "#111" },
  clearBtn:    { fontSize: 14, color: "#9ca3af", paddingLeft: 8 },
  resultCount: { fontSize: 13, color: "#6b7280", fontWeight: "600", paddingHorizontal: 16, marginBottom: 4 },
});

const c = StyleSheet.create({
  card:         { marginHorizontal: 16, marginVertical: 6, backgroundColor: "#fff", borderRadius: 16, padding: 16, shadowColor: "#000", shadowOpacity: 0.05, shadowRadius: 8, elevation: 2 },
  currentCard:  { borderWidth: 2, borderColor: "#10b981" },
  top:          { flexDirection: "row", alignItems: "flex-start", marginBottom: 10 },
  avatar:       { width: 48, height: 48, borderRadius: 24, backgroundColor: "#e0e7ff", alignItems: "center", justifyContent: "center", marginRight: 12 },
  namedAvatar:  { backgroundColor: "#1a1a1a" },
  avatarTxt:    { fontSize: 20, fontWeight: "700", color: "#4f46e5" },
  namedAvatarTxt: { color: "#fff" },
  nameRow:      { flexDirection: "row", alignItems: "center", gap: 6, flexWrap: "wrap" },
  name:         { fontSize: 16, fontWeight: "700", color: "#111" },
  username:     { fontSize: 12, color: "#9ca3af", marginTop: 1 },
  location:     { fontSize: 12, color: "#6b7280", marginTop: 2 },
  tierBadge:    { paddingHorizontal: 8, paddingVertical: 2, backgroundColor: "#f3f4f6", borderRadius: 20 },
  namedBadge:   { backgroundColor: "#1a1a1a" },
  tierTxt:      { fontSize: 10, fontWeight: "700", color: "#374151" },
  namedTxt:     { color: "#fff" },
  bio:          { fontSize: 13, color: "#6b7280", lineHeight: 18, marginBottom: 8 },
  tagsRow:      { flexDirection: "row", flexWrap: "wrap", gap: 6, marginBottom: 10 },
  tag:          { backgroundColor: "#eff6ff", paddingHorizontal: 10, paddingVertical: 3, borderRadius: 20 },
  tagTxt:       { fontSize: 11, color: "#3b82f6", fontWeight: "500" },
  bottom:       { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-end", marginTop: 4 },
  feeLabel:     { fontSize: 11, color: "#9ca3af", marginBottom: 2 },
  feeValue:     { fontSize: 15, fontWeight: "700", color: "#10b981" },
  namedFee:     { color: "#ef4444" },
  btnRow:       { flexDirection: "row", gap: 8 },
  consultBtn:   { paddingHorizontal: 12, paddingVertical: 9, borderRadius: 10, borderWidth: 1.5, borderColor: "#6366f1" },
  consultBtnTxt: { color: "#6366f1", fontWeight: "700", fontSize: 12 },
  matchBtn:     { backgroundColor: "#1a1a1a", paddingHorizontal: 14, paddingVertical: 9, borderRadius: 10 },
  matchBtnTxt:  { color: "#fff", fontWeight: "700", fontSize: 12 },
  btnDisabled:  { backgroundColor: "#e5e7eb", borderColor: "#e5e7eb" },
  btnTxtDisabled: { color: "#9ca3af" },
  currentBadge: { backgroundColor: "#d1fae5", paddingHorizontal: 12, paddingVertical: 7, borderRadius: 10 },
  currentBadgeTxt: { color: "#10b981", fontWeight: "700", fontSize: 13 },
});

const m = StyleSheet.create({
  container:  { flex: 1, backgroundColor: "#fff", padding: 24 },
  header:     { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 24 },
  title:      { fontSize: 20, fontWeight: "700", color: "#111" },
  closeBtn:   { padding: 4 },
  closeTxt:   { fontSize: 18, color: "#9ca3af" },
  instrCard:  { alignItems: "center", paddingVertical: 20, marginBottom: 20 },
  avatar:     { width: 64, height: 64, borderRadius: 32, backgroundColor: "#e0e7ff", alignItems: "center", justifyContent: "center", marginBottom: 8 },
  namedAvatar:    { backgroundColor: "#1a1a1a" },
  avatarTxt:      { fontSize: 26, fontWeight: "700", color: "#4f46e5" },
  namedAvatarTxt: { color: "#fff" },
  instrName:  { fontSize: 22, fontWeight: "700", color: "#111", marginTop: 6 },
  instrSub:   { fontSize: 13, color: "#9ca3af", marginTop: 2 },
  tierBadge:  { paddingHorizontal: 12, paddingVertical: 4, backgroundColor: "#f3f4f6", borderRadius: 20 },
  namedBadge: { backgroundColor: "#1a1a1a" },
  tierTxt:    { fontSize: 11, fontWeight: "700", color: "#374151" },
  namedTxt:   { color: "#fff" },
  feeBox:     { backgroundColor: "#fff7ed", borderRadius: 12, padding: 16, marginBottom: 20, alignItems: "center" },
  freeBox:    { backgroundColor: "#f0fdf4" },
  consultBox: { backgroundColor: "#eef2ff" },
  feeLabel:   { fontSize: 11, color: "#9ca3af", marginBottom: 4 },
  feeAmount:  { fontSize: 24, fontWeight: "800", color: "#ef4444", marginBottom: 4 },
  feeNote:    { fontSize: 11, color: "#9ca3af", textAlign: "center", lineHeight: 16 },
  freeTxt:    { fontSize: 18, fontWeight: "700", color: "#10b981", marginBottom: 4 },
  consultTitle: { fontSize: 18, fontWeight: "700", color: "#6366f1", marginBottom: 8 },
  label:      { fontSize: 13, fontWeight: "600", color: "#374151", marginBottom: 8 },
  input:      { borderWidth: 1, borderColor: "#d1d5db", borderRadius: 10, padding: 12, fontSize: 14, height: 90, textAlignVertical: "top", marginBottom: 24 },
  btns:       { flexDirection: "row", gap: 12 },
  cancelBtn:  { flex: 1, padding: 14, borderRadius: 10, borderWidth: 1, borderColor: "#d1d5db" },
  cancelTxt:  { textAlign: "center", color: "#374151", fontWeight: "600" },
  submitBtn:  { flex: 1, padding: 14, backgroundColor: "#1a1a1a", borderRadius: 10 },
  consultSubmitBtn: { backgroundColor: "#6366f1" },
  submitTxt:  { textAlign: "center", color: "#fff", fontWeight: "700" },
});
