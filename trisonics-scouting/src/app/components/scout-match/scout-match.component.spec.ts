import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ScoutMatchComponent } from './scout-match.component';

describe('ScoutMatchComponent', () => {
  let component: ScoutMatchComponent;
  let fixture: ComponentFixture<ScoutMatchComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ ScoutMatchComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(ScoutMatchComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
