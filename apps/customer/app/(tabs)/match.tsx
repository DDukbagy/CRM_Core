// app/(tabs)/match.tsx
import { useCallback, useRef, useState } from "react";
import { View, Text, ScrollView, Pressable, TextInput, ActivityIndicator, Modal, StyleSheet } from "react-native";
import { appAlert } from "@/lib/alert";
import { useFocusEffect, useRouter } from "expo-router";
import { apiFetch } from "@/lib/api";
import type { InstructorPublicRead, UserRead } from "@/types/api";

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

type TabType = "recommend" | "search";

export default function MatchScreen() {
  const router = useRouter();
  const [tab, setTab] = useState<TabType>("recommend");

  const [instructors, setInstructors] = useState<InstructorPublicRead[]>([]);
  const [me, setMe]                   = useState<UserRead | null>(null);
  const [loading, setLoading]         = useState(true);
  const initialLoaded                 = useRef(false);

  // 숨고식 단계별 매칭 wizard
  const [wizStep, setWizStep]           = useState(0);           // 0=purpose 1=location 2=results
  const [wizPurpose, setWizPurpose]     = useState<typeof PURPOSES[0] | null>(null);
  const [wizLocation, setWizLocation]   = useState<string | null>(null);

  // 강사 찾기 검색어
  const [searchText, setSearchText] = useState("");

  // 강사 상세 프로필 모달 → 문의하기
  const [profile, setProfile] = useState<InstructorPublicRead | null>(null);
  const [opening, setOpening] = useState(false);

  async function load() {
    try {
      const [meData, instrList] = await Promise.all([
        apiFetch<UserRead>("/users/me"),
        apiFetch<InstructorPublicRead[]>("/instructors/public"),
      ]);
      setMe(meData);
      setInstructors(instrList);
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

  // 문의하기: 강사와의 채팅방을 열고(이미 있으면 그 방) 채팅 탭으로 이동
  async function inquire(instructor: InstructorPublicRead) {
    setOpening(true);
    try {
      const room = await apiFetch<{ id: string }>("/chat/rooms", { method: "POST", body: { instructor_id: instructor.id } });
      setProfile(null);
      router.push({ pathname: "/(tabs)/chat", params: { room: room.id } } as any);
    } catch (e) {
      appAlert("오류", e instanceof Error ? e.message : "채팅방을 열지 못했습니다.");
    } finally {
      setOpening(false);
    }
  }

  function resetWizard() {
    setWizStep(0);
    setWizPurpose(null);
    setWizLocation(null);
  }

  if (loading) return <View style={s.center}><ActivityIndicator size="large" /></View>;

  return (
    <View style={{ flex: 1, backgroundColor: "#f9fafb" }}>

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
          me={me}
          onSelectPurpose={(p) => { setWizPurpose(p); setWizStep(1); }}
          onSelectLocation={(l) => { setWizLocation(l); setWizStep(2); }}
          onBack={() => setWizStep(s => Math.max(0, s - 1))}
          onReset={resetWizard}
          onSelect={setProfile}
        />
      ) : (
        <SearchTab
          instructors={searchList}
          searchText={searchText}
          onSearchChange={setSearchText}
          me={me}
          onSelect={setProfile}
        />
      )}

      {/* 강사 상세 프로필 */}
      <ProfileModal
        instructor={profile}
        isCurrentInstructor={!!profile && me?.manager_id === profile.id}
        opening={opening}
        onClose={() => setProfile(null)}
        onInquire={() => profile && inquire(profile)}
      />
    </View>
  );
}

// ── 숨고식 단계별 매칭 ────────────────────────────────────────
function WizardFlow({
  step, purpose, location, results, totalCount, me,
  onSelectPurpose, onSelectLocation, onBack, onReset, onSelect,
}: {
  step: number;
  purpose: typeof PURPOSES[0] | null;
  location: string | null;
  results: InstructorPublicRead[];
  totalCount: number;
  me: UserRead | null;
  onSelectPurpose: (p: typeof PURPOSES[0]) => void;
  onSelectLocation: (l: string) => void;
  onBack: () => void;
  onReset: () => void;
  onSelect: (i: InstructorPublicRead) => void;
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
            isCurrentInstructor={me?.manager_id === i.id}
            onPress={() => onSelect(i)}
          />
        ))
      )}
      <View style={{ height: 40 }} />
    </ScrollView>
  );
}

// ── 강사 찾기 탭 ─────────────────────────────────────────────
function SearchTab({
  instructors, searchText, onSearchChange, me, onSelect,
}: {
  instructors: InstructorPublicRead[];
  searchText: string;
  onSearchChange: (v: string) => void;
  me: UserRead | null;
  onSelect: (i: InstructorPublicRead) => void;
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
            isCurrentInstructor={me?.manager_id === i.id}
            onPress={() => onSelect(i)}
          />
        ))
      )}
      <View style={{ height: 40 }} />
    </ScrollView>
  );
}

// ── 강사 카드 ────────────────────────────────────────────────
function InstructorCard({
  instructor, isCurrentInstructor, onPress,
}: {
  instructor: InstructorPublicRead;
  isCurrentInstructor: boolean;
  onPress: () => void;
}) {
  const isNamed = instructor.instructor_tier === "NAMED";

  // 카드를 누르면 상세 프로필(문의하기)
  return (
    <Pressable style={[c.card, isCurrentInstructor && c.currentCard]} onPress={onPress}>
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
          <Text style={c.detailHint}>자세히 보기 ›</Text>
        )}
      </View>
    </Pressable>
  );
}

// ── 강사 상세 프로필 모달 (하단 "문의하기" → 채팅방) ─────────────
function ProfileModal({
  instructor, isCurrentInstructor, opening, onClose, onInquire,
}: {
  instructor: InstructorPublicRead | null;
  isCurrentInstructor: boolean;
  opening: boolean;
  onClose: () => void;
  onInquire: () => void;
}) {
  if (!instructor) return null;
  const isNamed = instructor.instructor_tier === "NAMED";

  return (
    <Modal visible animationType="slide" presentationStyle="pageSheet" onRequestClose={onClose}>
      <View style={m.container}>
        <View style={m.header}>
          <Text style={m.title}>강사 프로필</Text>
          <Pressable onPress={onClose} style={m.closeBtn}>
            <Text style={m.closeTxt}>✕</Text>
          </Pressable>
        </View>

        <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingBottom: 24 }}>
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
            <Text style={m.instrSub}>@{instructor.username}</Text>
            {instructor.location && <Text style={m.instrSub}>📍 {instructor.location}</Text>}
            {isCurrentInstructor && (
              <View style={[c.currentBadge, { marginTop: 8 }]}><Text style={c.currentBadgeTxt}>담당 강사</Text></View>
            )}
          </View>

          <View style={pf.section}>
            <ProfileRow label="경력" value={instructor.career_years ? `${instructor.career_years}년` : "-"} />
            <ProfileRow label="자격증" value={instructor.certifications || "-"} />
          </View>

          {instructor.specialties.length > 0 && (
            <View style={pf.section}>
              <Text style={pf.sectionTitle}>전문 분야</Text>
              <View style={c.tagsRow}>
                {instructor.specialties.map(sp => (
                  <View key={sp} style={c.tag}><Text style={c.tagTxt}>{sp}</Text></View>
                ))}
              </View>
            </View>
          )}

          <View style={pf.section}>
            <Text style={pf.sectionTitle}>소개</Text>
            <Text style={pf.bio}>{instructor.bio || "등록된 소개가 없습니다."}</Text>
          </View>
        </ScrollView>

        {/* 하단 고정: 문의하기 */}
        <View style={pf.footer}>
          <Pressable style={[pf.inquireBtn, opening && { opacity: 0.6 }]} onPress={onInquire} disabled={opening}>
            <Text style={pf.inquireTxt}>{opening ? "채팅방 여는 중..." : "문의하기"}</Text>
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}

function ProfileRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={pf.row}>
      <Text style={pf.rowLabel}>{label}</Text>
      <Text style={pf.rowValue}>{value}</Text>
    </View>
  );
}

const pf = StyleSheet.create({
  section:      { marginHorizontal: 20, marginTop: 16, backgroundColor: "#fff", borderRadius: 14, padding: 16, borderWidth: 1, borderColor: "#f3f4f6" },
  sectionTitle: { fontSize: 13, fontWeight: "700", color: "#6b7280", marginBottom: 10 },
  row:          { flexDirection: "row", justifyContent: "space-between", paddingVertical: 6 },
  rowLabel:     { fontSize: 14, color: "#6b7280" },
  rowValue:     { fontSize: 14, color: "#111", fontWeight: "600", flexShrink: 1, textAlign: "right", marginLeft: 12 },
  bio:          { fontSize: 14, color: "#374151", lineHeight: 21 },
  footer:       { padding: 16, paddingBottom: 28, borderTopWidth: 1, borderTopColor: "#f3f4f6", backgroundColor: "#fff" },
  inquireBtn:   { backgroundColor: "#16a34a", borderRadius: 14, paddingVertical: 16, alignItems: "center" },
  inquireTxt:   { color: "#fff", fontSize: 16, fontWeight: "700" },
});

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
  detailHint:   { fontSize: 13, color: "#16a34a", fontWeight: "600" },
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
